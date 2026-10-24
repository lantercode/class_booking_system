# F4.2 — 静态验证报告

> 日期：2026-09-29

## 1. py_compile

```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
  src/app/modules/order/models.py \
  alembic/versions/f42cd3e4f5a6_restore_orders_membership_card_fk_and_index.py \
  tests/integration/test_order_fk_membership_card.py && echo "COMPILE_OK_ALL"
```

实际执行：

```
$ cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
    src/app/modules/order/models.py \
    alembic/versions/f42cd3e4f5a6_restore_orders_membership_card_fk_and_index.py \
    tests/integration/test_order_fk_membership_card.py && echo "COMPILE_OK_ALL"
COMPILE_OK_ALL
```

> IDE 报 "无法解析导入 sqlalchemy/pytest/app.*" 为 linter 未识别 venv 的误报，py_compile 在 venv 下通过。

## 2. 模型与 migration 一致性核查

```bash
grep -n "membership_card_id\|ForeignKey\|ondelete\|Index(" \
  apps/api/src/app/modules/order/models.py
```

`Order.membership_card_id` 与 `__table_args__`（L58-69）：

| 行 | 代码 | 结论 |
|----|------|------|
| L58-63 | `membership_card_id: Mapped[int \| None] = mapped_column(BigInteger, ForeignKey("membership_cards.id", ondelete="SET NULL"), nullable=True, comment="关联会员卡ID（购买次卡时生成）")` | 模型补回 FK，与 migration `ondelete="SET NULL"` 一致 |
| L68 | `Index("ix_orders_membership_card_id", "membership_card_id")` | 模型声明索引，与 migration `create_index` 一致 |

migration（`f42cd3e4f5a6_*`）：

| 项 | 代码 | 结论 |
|----|------|------|
| revision | `revision: str = "f42cd3e4f5a6"` | 12 hex |
| down_revision | `down_revision: str \| Sequence[str] \| None = "f41ab2c3d4e5"` | 指向 F4.1 后唯一 head |
| upgrade 清理 | `op.execute(sa.text("UPDATE orders SET membership_card_id = NULL WHERE membership_card_id IS NOT NULL AND membership_card_id NOT IN (SELECT id FROM membership_cards)"))` | T4.2.1 前置 |
| upgrade 建 FK | `op.create_foreign_key(constraint_name=FK_NAME, source_table="orders", referent_table="membership_cards", local_cols=["membership_card_id"], remote_cols=["id"], ondelete="SET NULL")` | T4.2.1，与模型一致 |
| upgrade 建索引 | `op.create_index(index_name=INDEX_NAME, table_name="orders", columns=["membership_card_id"])` | T4.2.2，与模型一致 |
| downgrade | `op.drop_index(...)` + `op.drop_constraint(..., type_="foreignkey")` | 可逆（先 index 后 FK，反序） |

**结论**：模型 `ForeignKey("membership_cards.id", ondelete="SET NULL")` + `Index("ix_orders_membership_card_id", "membership_card_id")` 与 migration `create_foreign_key(..., ondelete="SET NULL")` + `create_index(...)` 完全一致；约束名 `fk_orders_membership_card_id` 与索引名 `ix_orders_membership_card_id` 在两处一致。

## 3. 分层合规检查

```bash
# 确认 Service/Repository 零改动（本 Feature 改动面白名单）
git status --short -- \
  apps/api/src/app/modules/order/service.py \
  apps/api/src/app/modules/order/repository.py \
  apps/api/src/app/modules/order/router.py \
  apps/api/src/app/modules/order/schemas.py \
  apps/api/src/app/modules/payment/service.py
# 无输出（这些文件未改动；order 模块当前仅有 models.py）
```

| 规则 | 检查 | 结果 |
|------|------|------|
| Service/Repository 零改动 | `git status` 显示 order/service.py / repository.py / router.py / schemas.py / payment/service.py 均未动（order 模块仅 models.py 存在） | 通过 |
| migration 走 Alembic | 用 `op.execute` + `op.create_foreign_key` + `op.create_index` / `op.drop_index` + `op.drop_constraint`，非手写 SQL 脚本 | 通过 |
| 事务边界 | 清理 UPDATE + ADD CONSTRAINT + CREATE INDEX 在同一 migration upgrade（alembic `Will assume transactional DDL`） | 通过 |
| 不裸 SQL 直写业务数据 | Service/Repository 无改动；migration 内 SQL 是结构变更清理，非业务读写 | 通过 |
| 租户隔离 | FK 是跨租户引用完整性（`membership_cards.id` 全局主键）；索引不含 tenant_id 前缀（用于 FK 触发器行定位 + 按卡反查）；`TenantAwareRepository` 的 `tenant_id` 过滤语义不变 | 通过 |
| RBAC | 无端点变更；`@require_permissions` 未动 | 通过 |
| 认证 | 无端点变更；`get_current_user` 未动 | 通过 |
| AI 边界 | 不涉及 MCP（无 Tool 变更） | 通过 |

## 4. 改动落点核查（grep 改动面白名单）

```bash
git status --short
```

本 Feature 实际触碰：

| 文件 | 本 Feature 实际变化 | 审查结论 |
|------|------|---------|
| `apps/api/alembic/versions/f42cd3e4f5a6_restore_orders_membership_card_fk_and_index.py` | 新建 migration | 清理孤立 + 建 FK（ON DELETE SET NULL）+ 建索引，down_revision=f41ab2c3d4e5 |
| `apps/api/src/app/modules/order/models.py` | `membership_card_id` 补 `ForeignKey` + `__table_args__` 补 `Index` | 模型与 migration 一致 |
| `apps/api/tests/integration/test_order_fk_membership_card.py` | 新建 | 7 用例覆盖 AC-1~AC-7 |

Service / Repository / Router / schemas / OpenAPI / 前端 / MCP / payment service **均未改动**。

## 5. revision 链核查

```bash
cd apps/api && PYTHONPATH=src .venv/bin/alembic heads
# 本 Feature 前：f41ab2c3d4e5 (head)   ← F4.1 后
# 本 Feature 后：f42cd3e4f5a6 (head)   ← 单 head（无分叉）
```

- `down_revision="f41ab2c3d4e5"` 指向 F4.1 后的唯一 head。
- 新 migration 应用后 `alembic heads` 仍为单 head `f42cd3e4f5a6`，无分叉。

## 6. DB 事实核查（migration 前后对比）

| 指标 | migration 前 | migration 后 |
|------|-------------|-------------|
| orders 总数 | 0 | 0（不变） |
| membership_card_id 非空数 | 0 | 0（不变） |
| 孤立计数 | 0 | 0（dev 库原本 0；防御性清理 0 行受影响） |
| FK `fk_orders_membership_card_id` | 不存在 | 存在，`ON DELETE SET NULL` |
| Index `ix_orders_membership_card_id` | 不存在 | 存在，`btree (membership_card_id)` |
| alembic_version | `f41ab2c3d4e5` | `f42cd3e4f5a6` |

实测 SQL：
```sql
-- FK 定义
SELECT pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid='orders'::regclass AND conname='fk_orders_membership_card_id';
-- → FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id) ON DELETE SET NULL

-- 索引定义
SELECT indexdef FROM pg_indexes
WHERE tablename='orders' AND indexname='ix_orders_membership_card_id';
-- → CREATE INDEX ix_orders_membership_card_id ON public.orders USING btree (membership_card_id)

-- 孤立计数
SELECT COUNT(*) FROM orders o LEFT JOIN membership_cards m ON o.membership_card_id=m.id
WHERE o.membership_card_id IS NOT NULL AND m.id IS NULL;
-- → 0
```

## 7. migration 可逆性验证（AC-10 手动）

```bash
cd apps/api && PYTHONPATH=src .venv/bin/alembic downgrade -1
# → Running downgrade f42cd3e4f5a6 -> f41ab2c3d4e5
# 验证：FK 不存在、Index 不存在、alembic_version=f41ab2c3d4e5
# 实测：FK exists= None, Index exists= None, alembic_version= f41ab2c3d4e5

cd apps/api && PYTHONPATH=src .venv/bin/alembic upgrade head
# → Running upgrade f41ab2c3d4e5 -> f42cd3e4f5a6
# 验证：FK 存在（ON DELETE SET NULL）、Index 存在、alembic_version=f42cd3e4f5a6
# 实测：FK=FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id) ON DELETE SET NULL
#       Index=CREATE INDEX ix_orders_membership_card_id ON public.orders USING btree (membership_card_id)
#       alembic_version=f42cd3e4f5a6
```

往返成功，证明 upgrade/downgrade 均可重复执行。

## 8. 契约一致性

- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变（无端点变更）。
- 模型列 `membership_card_id` 类型仍为 `BigInteger`（nullable=True），仅新增 FK 元数据 → DTO 字段集合不变。
- `__table_args__` 新增 `Index` 不影响 DTO 字段集合。
- 前端 4 端影响评估：
  - admin-web / teacher-web / student-web / miniapp：不直接感知 DB FK / 索引；订单/支付端点契约不变（order 模块当前无 router） → **均不涉及**。
- 无需 `pnpm gen:types`。

## 9. 异常处理一致性

- DB 层 FK 违反抛 `IntegrityError`（SQLAlchemy），不直接透传前端。
- order 模块当前无 Service / Router（仅有 models.py），无 ORM 创建 Order 的业务路径；即便未来支付流程创建 Order 时 FK 触发 `IntegrityError`，经全局异常处理器返回统一信封 `{code:500, msg, data:null}`，不回显 SQL / traceback / 异常类型字符串（见 AC-4 测试断言 `pytest.raises(IntegrityError)`，由全局处理器捕获）。
