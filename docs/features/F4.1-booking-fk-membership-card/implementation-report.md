# F4.1 — 恢复 bookings.membership_card_id 外键 · 实施报告

> 日期：2026-09-29 ｜ 执行：database-engineer
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

按 [implementation-plan.md](./implementation-plan.md) 完成 F4.1 两个子任务：
- **T4.1.1**：清理孤立 booking（`membership_card_id` 指向不存在的卡）→ 用 migration 内 `UPDATE ... SET NULL WHERE ... NOT IN (SELECT id FROM membership_cards)`，实测 4 条孤立全部置 NULL。
- **T4.1.2**：migration 加外键 `fk_bookings_membership_card_id`（`ON DELETE SET NULL`）→ `op.create_foreign_key(..., ondelete="SET NULL")`。

同时把 ORM 模型 `Booking.membership_card_id` 由纯 `BigInteger` 补回 `ForeignKey("membership_cards.id", ondelete="SET NULL")`，使模型与 DB 一致。Service / Repository / Router / schemas / OpenAPI / 前端 / MCP 均未改动。

## 2. 变更明细

### 2.1 `apps/api/alembic/versions/f41ab2c3d4e5_restore_bookings_membership_card_fk.py`（新建）

| 项 | 值 |
|----|----|
| revision | `f41ab2c3d4e5` |
| down_revision | `211f847af16c`（当前唯一 head） |
| upgrade | (1) `UPDATE bookings SET membership_card_id = NULL WHERE membership_card_id IS NOT NULL AND membership_card_id NOT IN (SELECT id FROM membership_cards)`；(2) `op.create_foreign_key("fk_bookings_membership_card_id", "bookings", "membership_cards", ["membership_card_id"], ["id"], ondelete="SET NULL")` |
| downgrade | `op.drop_constraint("fk_bookings_membership_card_id", "bookings", type_="foreignkey")`（不恢复孤立数据） |

要点：
- 清理 + 建 FK 在同一事务（alembic `Will assume transactional DDL`），原子完成。
- 约束名显式 `fk_bookings_membership_card_id`，便于 downgrade 精确 drop。
- `down_revision` 指向 `211f847af16c`（merge_heads_for_frozen_remaining_days），revision 链不断裂。

### 2.2 `apps/api/src/app/modules/booking/models.py`（L52-56）

| 改动点 | 修复前 | 修复后 |
|--------|---------|---------|
| `membership_card_id` 列定义 | `mapped_column(BigInteger, nullable=True)` | `mapped_column(BigInteger, ForeignKey("membership_cards.id", ondelete="SET NULL"), nullable=True)` |

`ForeignKey` 已在第 5 行 import，无需新增导入。

### 2.3 `apps/api/tests/integration/test_booking_fk_membership_card.py`（新建）

- session-scoped `shared_data` fixture：解析种子 IDs（tenant/student/teacher/admin）+ 创建 1 共享 course；engine 在 fixture 内 dispose，只返回纯数据 dict。
- function-scoped `local_db` fixture：每用例独立 engine + session_factory。
- helper：`_create_schedule` / `_create_card` / `_create_booking` / `_cleanup`（清理时先删 txn 再删 card，避免 FK 阻塞）。
- 6 用例覆盖 AC-1~AC-6：
  - `test_fk_constraint_exists_with_on_delete_set_null`（AC-1）
  - `test_booking_with_valid_membership_card_succeeds`（AC-2）
  - `test_booking_with_nonexistent_card_raises_integrity_error`（AC-3）
  - `test_delete_card_sets_booking_card_id_null`（AC-4）
  - `test_no_orphan_bookings_after_migration`（AC-5）
  - `test_migration_cleanup_clears_orphan_and_readds_fk`（AC-6，事务内复刻 upgrade，最终 rollback 不污染 dev DB）

## 3. 实施中发现的问题

| # | 问题 | 处置 |
|---|------|------|
| 1 | init migration `4bd04b738098` 原本定义了该 FK（`ondelete="SET NULL"`），但当前 DB 与模型都丢失 | 确认"恢复"语义：本 Feature 不是新增设计，而是恢复原设计；migration 与模型均按原 `ON DELETE SET NULL` 恢复 |
| 2 | 直接 `ADD CONSTRAINT` 会因 4 条孤立失败 | migration 先 `UPDATE` 清理再 `ADD CONSTRAINT`，同一事务原子完成 |
| 3 | AC-6 测试需构造孤立 booking，但 FK 已建后无法插入孤立 | 在显式事务内先 `DROP CONSTRAINT IF EXISTS` → 插孤立 → 验证 → 清理 UPDATE → 验证 NULL → re-add FK → `trans.rollback()` 还原；PostgreSQL DDL 事务化保证不污染 dev DB |

## 4. 与计划的偏差

- 计划列出的 3 个文件（migration + model + 测试）全部按方案交付，无新增计划外源文件改动。
- AC-6 测试设计采用"事务内复刻 upgrade + rollback"而非真实 `alembic downgrade/upgrade` 往返，避免在共享 dev DB 上反复 drop/add 全局约束影响其他连接；`alembic downgrade -1 + upgrade head` 往返已作为 AC-9 单独手动验证（见 static-verification.md 第 7 节）。

## 5. 数据兼容与迁移

- **DB 结构变更**：新增 FK `fk_bookings_membership_card_id`（`ON DELETE SET NULL`）。
- **数据变更**：4 条孤立 `bookings.membership_card_id` 由不存在卡 ID 置 NULL（语义为"无关联卡"）。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。
- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变 → 无需 `pnpm gen:types`，前端 4 端无影响。
- migration 可逆（`downgrade` drop FK；不恢复孤立数据，见 UNKNOWN U3）。

## 6. 测试结果

- `test_booking_fk_membership_card.py`：**6 passed**（0.37s）
- 回归 `test_cancel_schedule_rollback.py` + `test_booking_ownership.py` + `test_checkin_complete_lock.py`：**31 passed**（9.11s）
- migration 可逆性（`alembic downgrade -1` + `alembic upgrade head`）：往返成功，孤立=0，FK 恢复。
- py_compile（model + migration + test）：`COMPILE_OK_ALL`。

详见 [runtime-test-report.md](./runtime-test-report.md) 与 [static-verification.md](./static-verification.md)。
