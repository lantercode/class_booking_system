# F4.1 — 运行时测试报告

> 日期：2026-09-29
> 环境：本地开发机，PostgreSQL（Docker 共享开发库，预置种子租户 dance-school），Redis 可用。migration `f41ab2c3d4e5` 已 apply（alembic_version=f41ab2c3d4e5）。

## 1. 测试入口

```bash
# 主测试（F4.1）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_fk_membership_card.py -v

# 回归（AC-7）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest \
  tests/integration/test_cancel_schedule_rollback.py \
  tests/integration/test_booking_ownership.py \
  tests/integration/test_checkin_complete_lock.py -v
```

## 2. 结果摘要

| 套件 | 结果 |
|------|------|
| `test_booking_fk_membership_card.py` | **6 passed**（0.37s） |
| `test_cancel_schedule_rollback.py`（回归） | **12 passed** |
| `test_booking_ownership.py`（回归） | **10 passed** |
| `test_checkin_complete_lock.py`（回归） | **9 passed** |
| **合计** | **37 passed, 4 warnings** |

warnings 均为既有第三方库 deprecation（passlib `crypt`、uvicorn/websockets legacy、FastAPI `example`），与本 Feature 无关。

## 3. 用例明细（test_booking_fk_membership_card.py，6/6 通过）

### 3.1 TestBookingFkMembershipCard（FK 行为验证，5/5）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_fk_constraint_exists_with_on_delete_set_null` | AC-1 | 查询 `pg_constraint` 取 `fk_bookings_membership_card_id` 的 `pg_get_constraintdef`；定义含 `FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id)` 与 `ON DELETE SET NULL` |
| `test_booking_with_valid_membership_card_succeeds` | AC-2 | 落库 1 schedule + 1 ACTIVE card + 1 BOOKED booking（card_id 指向该卡）；不抛异常；重读 booking `membership_card_id == card_id` |
| `test_booking_with_nonexistent_card_raises_integrity_error` | AC-3 | `session.add(Booking(membership_card_id=999999999))` + `commit` → `pytest.raises(IntegrityError)`；重查 `membership_card_id=999999999` 的 booking 为空（未落库） |
| `test_delete_card_sets_booking_card_id_null` | AC-4 | 落库 schedule + card + booking（引用该卡）；`DELETE FROM membership_cards WHERE id=card_id`；重读 booking 仍存在且 `membership_card_id is None`（ON DELETE SET NULL） |
| `test_no_orphan_bookings_after_migration` | AC-5 | `SELECT COUNT(*) ... LEFT JOIN membership_cards ... WHERE membership_card_id IS NOT NULL AND m.id IS NULL` → `== 0` |

### 3.2 TestBookingFkMigrationLogic（migration 清理逻辑，1/1）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_migration_cleanup_clears_orphan_and_readds_fk` | AC-6 | 显式事务内：drop FK → 插孤立 booking（card_id=999999999，复用种子 schedule/student ID，status=CANCELLED 规避唯一约束）→ 验证孤立存在 → 执行清理 UPDATE → 验证 card_id 变 NULL → re-add FK 成功 → `trans.rollback()` 还原；二次确认 dev DB 无残留测试 booking |

## 4. 测试可信度分析

### 4.1 测试逻辑的区分力

- **migration 未应用前**：`test_fk_constraint_exists_with_on_delete_set_null` 查不到 FK → 失败；`test_booking_with_nonexistent_card_raises_integrity_error` 插入 card_id=999999999 不抛 IntegrityError（无 FK） → 失败；`test_no_orphan_bookings_after_migration` 孤立计数=4≠0 → 失败。
- **migration 应用后**：上述 3 用例全部通过 → 证明 FK 已建 + 孤立已清。
- 若回退本 Feature（drop FK），`test_fk_constraint_exists_with_on_delete_set_null` / `test_booking_with_nonexistent_card_raises_integrity_error` / `test_no_orphan_bookings_after_migration` 必失败。

### 4.2 真实 DB 事务性保障

- AC-2/AC-3/AC-4：用独立 `AsyncSession` 落库 + commit，再用新 session 读 DB 验证终态（避免读到 dirty session）。
- AC-3 的 `IntegrityError` 由 PostgreSQL FK 校验在 commit 时抛出（asyncpg → SQLAlchemy），非 mock。
- AC-4 的 `ON DELETE SET NULL` 由 PostgreSQL FK 触发器在 `DELETE FROM membership_cards` 时执行 `UPDATE bookings`，跨连接生效。

### 4.3 AC-6 的事务隔离设计

- 用 `engine.connect()` + `conn.begin()` 显式事务，所有 DDL（DROP/ADD CONSTRAINT）+ DML（INSERT/UPDATE）在同一事务内。
- PostgreSQL DDL 事务化：事务未 commit 前，并发连接看到旧状态（FK 仍在），仅本事务内可见 drop；`trans.rollback()` 还原，dev DB 无残留。
- 二次确认：rollback 后 `SELECT * FROM bookings WHERE id=<测试 booking_id>` 为空（INSERT 被回滚）。
- 复用种子 booking 的 `schedule_id`/`student_id`/`tenant_id` 插孤立 booking，`status=CANCELLED`（=2）规避 `uq_bookings_schedule_student_active` 唯一约束（仅覆盖 status IN (1,3,4)）。

### 4.4 事件循环隔离（借鉴 F2.4）

- `shared_data`（session-scoped）在 session loop 内创建并 dispose engine，只返回纯数据 dict。
- `local_db`（function-scoped）为每用例独立 engine + session_factory。
- AC-6 用独立 `create_async_engine` 在用例内完成，结束后 `engine.dispose()`。

6/6 全绿，无跨 loop 错误。

## 5. 回归结论

- `test_cancel_schedule_rollback.py`（12/12）+ `test_booking_ownership.py`（10/10）+ `test_checkin_complete_lock.py`（9/9）全部通过 → **AC-7 满足**。
- 取消排期回补课时（F2.4）、预约归属（F2.2）、签到/完成行锁（F2.3）行为未受本 Feature 影响。
- 本 Feature 仅在 DB 层加 FK + 清理孤立，Service/Repository 零改动 → 业务逻辑零回归风险。
- 关键：`if booking.membership_card_id:` 短路模式在 4 条孤立被置 NULL 后仍正确工作（这些 booking 指向的卡本不存在，置 NULL 后跳过 restore_credit，与"无卡预约"一致）。

## 6. 性能与资源

- 6 个主测试用例约 0.37s（含 fixture 一次性搭建共享 course + 每用例独立 schedule/card/booking 创建/清理）。
- `ON DELETE SET NULL` 触发时按 `membership_card_id` 定位引用行：bookings 量级小（11 行），顺序扫描足够；高量级时建议加索引（另立 Feature）。
- 全部 37 用例（含回归）约 9.5s（0.37s + 9.11s），无慢查询告警。

## 7. 迭代记录

| 轮次 | 问题 | 修复 |
|------|------|------|
| 第 1 轮 | — | **6/6 通过**（首版即全绿，无迭代） |
