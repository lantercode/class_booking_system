# F4.1 — 静态验证报告

> 日期：2026-09-29

## 1. py_compile

```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
  src/app/modules/booking/models.py \
  alembic/versions/f41ab2c3d4e5_restore_bookings_membership_card_fk.py \
  tests/integration/test_booking_fk_membership_card.py
# → COMPILE_OK_ALL（全部通过，无输出错误）
```

实际执行：

```
$ cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
    src/app/modules/booking/models.py \
    alembic/versions/f41ab2c3d4e5_restore_bookings_membership_card_fk.py \
    tests/integration/test_booking_fk_membership_card.py && echo "COMPILE_OK_ALL"
COMPILE_OK_ALL
```

> IDE 报 "无法解析导入 sqlalchemy/pytest" 为 linter 未识别 venv 的误报，py_compile 在 venv 下通过。

## 2. 模型与 migration 一致性核查

```bash
grep -n "membership_card_id\|ForeignKey\|ondelete" \
  apps/api/src/app/modules/booking/models.py
```

`Booking.membership_card_id`（L52-56）：

| 行 | 代码 | 结论 |
|----|------|------|
| L52-56 | `membership_card_id: Mapped[int \| None] = mapped_column(BigInteger, ForeignKey("membership_cards.id", ondelete="SET NULL"), nullable=True)` | ✅ 模型补回 FK，与 migration `ondelete="SET NULL"` 一致 |

migration（`f41ab2c3d4e5_*`）：

| 项 | 代码 | 结论 |
|----|------|------|
| revision | `revision: str = "f41ab2c3d4e5"` | ✅ 12 hex |
| down_revision | `down_revision: str \| Sequence[str] \| None = "211f847af16c"` | ✅ 指向当前唯一 head |
| upgrade 清理 | `op.execute(sa.text("UPDATE bookings SET membership_card_id = NULL WHERE membership_card_id IS NOT NULL AND membership_card_id NOT IN (SELECT id FROM membership_cards)"))` | ✅ T4.1.1 |
| upgrade 建 FK | `op.create_foreign_key(constraint_name=FK_NAME, source_table="bookings", referent_table="membership_cards", local_cols=["membership_card_id"], remote_cols=["id"], ondelete="SET NULL")` | ✅ T4.1.2，与模型一致 |
| downgrade | `op.drop_constraint(constraint_name=FK_NAME, table_name="bookings", type_="foreignkey")` | ✅ 可逆（不恢复孤立数据） |

**结论**：模型 `ForeignKey("membership_cards.id", ondelete="SET NULL")` 与 migration `create_foreign_key(..., ondelete="SET NULL")` 完全一致；约束名 `fk_bookings_membership_card_id` 在两处一致。

## 3. 分层合规检查

```bash
# 确认 Service/Repository 零改动（本 Feature 改动面白名单）
git status --short -- apps/api/src/app/modules/booking/service.py apps/api/src/app/modules/booking/repository.py apps/api/src/app/modules/schedule/service.py
# 无输出（这些文件未改动）
```

| 规则 | 检查 | 结果 |
|------|------|------|
| Service/Repository 零改动 | `git status` 显示 booking/service.py / booking/repository.py / schedule/service.py 均未动 | ✅ |
| migration 走 Alembic | 用 `op.execute` + `op.create_foreign_key` / `op.drop_constraint`，非手写 SQL 脚本 | ✅ |
| 事务边界 | 清理 UPDATE + ADD CONSTRAINT 在同一 migration upgrade（alembic `Will assume transactional DDL`） | ✅ |
| 不裸 SQL 直写业务数据 | Service/Repository 无改动；migration 内 SQL 是结构变更清理，非业务读写 | ✅ |
| 租户隔离 | FK 是跨租户引用完整性（`membership_cards.id` 全局主键）；`TenantAwareRepository` 的 `tenant_id` 过滤语义不变 | ✅ |
| RBAC | 无端点变更；`@require_permissions` 未动 | ✅ |
| 认证 | 无端点变更；`get_current_user` 未动 | ✅ |
| AI 边界 | 不涉及 MCP（无 Tool 变更） | ✅ |

## 4. 改动落点核查（grep 改动面白名单）

```bash
git status --short
```

本 Feature 实际触碰：

| 文件 | 本 Feature 实际变化 | 审查结论 |
|------|------|---------|
| `apps/api/alembic/versions/f41ab2c3d4e5_restore_bookings_membership_card_fk.py` | 新建 migration | 清理孤立 + 建 FK（ON DELETE SET NULL），down_revision=211f847af16c |
| `apps/api/src/app/modules/booking/models.py` | `membership_card_id` 补 `ForeignKey("membership_cards.id", ondelete="SET NULL")` | 模型与 migration 一致 |
| `apps/api/tests/integration/test_booking_fk_membership_card.py` | 新建 | 6 用例覆盖 AC-1~AC-6 |

Service / Repository / Router / schemas / OpenAPI / 前端 / MCP **均未改动**。

## 5. revision 链核查

```bash
cd apps/api && PYTHONPATH=src .venv/bin/alembic heads
# → 211f847af16c (head)   ← 本 Feature 前
# 应用 migration后：
# → f41ab2c3d4e5 (head)   ← 本 Feature 后（单 head）
```

- `down_revision="211f847af16c"` 指向本 Feature 前的唯一 head。
- 新 migration 应用后 `alembic heads` 仍为单 head `f41ab2c3d4e5`，无分叉。

## 6. DB 事实核查（migration 前后对比）

| 指标 | migration 前 | migration 后 |
|------|-------------|-------------|
| bookings 总数 | 11 | 11（不变） |
| membership_card_id 非空数 | 10 | 6（4 条孤立被置 NULL） |
| 孤立计数 | 4 | 0 |
| FK `fk_bookings_membership_card_id` | 不存在 | 存在，`ON DELETE SET NULL` |
| alembic_version | `211f847af16c` | `f41ab2c3d4e5` |

实测 SQL：
```sql
-- FK 定义
SELECT pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid='bookings'::regclass AND conname='fk_bookings_membership_card_id';
-- → FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id) ON DELETE SET NULL

-- 孤立计数
SELECT COUNT(*) FROM bookings b LEFT JOIN membership_cards m ON b.membership_card_id=m.id
WHERE b.membership_card_id IS NOT NULL AND m.id IS NULL;
-- → 0
```

## 7. migration 可逆性验证（AC-9 手动）

```bash
cd apps/api && PYTHONPATH=src .venv/bin/alembic downgrade -1
# → Running downgrade f41ab2c3d4e5 -> 211f847af16c
# 验证：FK 不存在，alembic_version=211f847af16c

cd apps/api && PYTHONPATH=src .venv/bin/alembic upgrade head
# → Running upgrade 211f847af16c -> f41ab2c3d4e5
# 验证：FK 存在（ON DELETE SET NULL），alembic_version=f41ab2c3d4e5，孤立=0
```

往返成功，证明 upgrade/downgrade 均可重复执行。

## 8. 契约一致性

- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变（无端点变更）。
- 模型列 `membership_card_id` 类型仍为 `BigInteger`（nullable=True），仅新增 FK 元数据 → DTO 字段集合不变。
- 前端 4 端影响评估：
  - admin-web / teacher-web / student-web / miniapp：不直接感知 DB FK；创建预约端点契约不变 → **均不涉及**。
- 无需 `pnpm gen:types`。

## 9. 异常处理一致性

- DB 层 FK 违反抛 `IntegrityError`（SQLAlchemy），不直接透传前端。
- 业务层 Service 在创建 booking 前已校验 card 有效性（既有逻辑），DB FK 为最后兜底。
- 即便 FK 触发，经全局异常处理器返回统一信封 `{code:500, msg, data:null}`，不回显 SQL / traceback / 异常类型字符串（见 AC-3 测试断言 `pytest.raises(IntegrityError)`，由 Service/全局处理器捕获）。
