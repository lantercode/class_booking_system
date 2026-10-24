# F4.2 — 恢复 orders.membership_card_id 外键 + 索引 · 实施报告

> 日期：2026-09-29 ｜ 执行：database-engineer
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

按 [implementation-plan.md](./implementation-plan.md) 完成 F4.2 两个子任务：
- **T4.2.1**：migration 加外键 `fk_orders_membership_card_id`（`ON DELETE SET NULL`）→ 同一事务内先 `UPDATE ... SET NULL WHERE ... NOT IN (SELECT id FROM membership_cards)` 防御性清理孤立（dev 库当前 0 条），再 `op.create_foreign_key(..., ondelete="SET NULL")`。
- **T4.2.2**：加索引 `ix_orders_membership_card_id` → `op.create_index("ix_orders_membership_card_id", "orders", ["membership_card_id"])`。

同时把 ORM 模型 `Order.membership_card_id` 由纯 `BigInteger` 补回 `ForeignKey("membership_cards.id", ondelete="SET NULL")`，并在 `__table_args__` 补 `Index("ix_orders_membership_card_id", "membership_card_id")`，使模型与 DB 一致。Service / Repository / Router / schemas / OpenAPI / 前端 / MCP 均未改动。

## 2. 变更明细

### 2.1 `apps/api/alembic/versions/f42cd3e4f5a6_restore_orders_membership_card_fk_and_index.py`（新建）

| 项 | 值 |
|----|----|
| revision | `f42cd3e4f5a6` |
| down_revision | `f41ab2c3d4e5`（F4.1 后唯一 head） |
| upgrade | (1) `UPDATE orders SET membership_card_id = NULL WHERE membership_card_id IS NOT NULL AND membership_card_id NOT IN (SELECT id FROM membership_cards)`；(2) `op.create_foreign_key("fk_orders_membership_card_id", "orders", "membership_cards", ["membership_card_id"], ["id"], ondelete="SET NULL")`；(3) `op.create_index("ix_orders_membership_card_id", "orders", ["membership_card_id"])` |
| downgrade | (1) `op.drop_index("ix_orders_membership_card_id", "orders")`；(2) `op.drop_constraint("fk_orders_membership_card_id", "orders", type_="foreignkey")`（不恢复孤立数据） |

要点：
- 清理 + 建 FK + 建索引在同一事务（alembic `Will assume transactional DDL`），原子完成。
- 约束名显式 `fk_orders_membership_card_id`，索引名显式 `ix_orders_membership_card_id`，便于 downgrade 精确 drop。
- `down_revision` 指向 `f41ab2c3d4e5`（F4.1），revision 链不断裂。
- downgrade 顺序与 upgrade 反序：先 drop index 再 drop FK（更安全可审计）。

### 2.2 `apps/api/src/app/modules/order/models.py`（L58-69）

| 改动点 | 修复前 | 修复后 |
|--------|---------|---------|
| `membership_card_id` 列定义 | `mapped_column(BigInteger, nullable=True, comment="关联会员卡ID（购买次卡时生成）")` | `mapped_column(BigInteger, ForeignKey("membership_cards.id", ondelete="SET NULL"), nullable=True, comment="关联会员卡ID（购买次卡时生成）")` |
| `__table_args__` | 2 个 Index（`idx_orders_user` + `idx_orders_status_created`） | 3 个 Index（新增 `Index("ix_orders_membership_card_id", "membership_card_id")`） |

`ForeignKey` 与 `Index` 已在文件顶部 import（L8-9），无需新增导入。

### 2.3 `apps/api/tests/integration/test_order_fk_membership_card.py`（新建）

- session-scoped `shared_data` fixture：解析种子 IDs（tenant/student/teacher/admin），返回纯数据 dict；engine 在 fixture 内 dispose。
- function-scoped `local_db` fixture：每用例独立 engine + session_factory。
- helper：`_gen_order_no` / `_gen_card_no`（TEST- 前缀便于兜底清理识别）/ `_create_card` / `_create_order` / `_cleanup`（先删 order 再清理 card 的 txn 再删 card）。
- 7 用例覆盖 AC-1~AC-7：
  - `test_fk_constraint_exists_with_on_delete_set_null`（AC-1）
  - `test_index_on_membership_card_id_exists`（AC-2）
  - `test_order_with_valid_membership_card_succeeds`（AC-3）
  - `test_order_with_nonexistent_card_raises_integrity_error`（AC-4）
  - `test_delete_card_sets_order_card_id_null`（AC-5）
  - `test_no_orphan_orders_after_migration`（AC-6）
  - `test_migration_cleanup_clears_orphan_and_readds_fk`（AC-7，事务内复刻 upgrade，最终 rollback 不污染 dev DB）

## 3. 实施中发现的问题

| # | 问题 | 处置 |
|---|------|------|
| 1 | `57aeb9dcf020` migration 新增 `orders.membership_card_id` 列时仅落库 BigInteger 无 FK | 确认"恢复"语义：本 Feature 与 F4.1 同范式（建列时遗漏 FK，后续 migration 补回）；本 Feature 额外补索引（Task T4.2.2 要求） |
| 2 | 直接 `ADD CONSTRAINT` 在 dev 库当前可成功（无孤立），但生产可能非 0 | migration 仍先 `UPDATE` 防御性清理再 `ADD CONSTRAINT`，同一事务原子完成；dev 库 0 行受影响，生产若有孤立也安全 |
| 3 | AC-7 测试需构造孤立 order，但 FK 已建后无法插入孤立 | 在显式事务内先 `DROP CONSTRAINT IF EXISTS` → 插孤立 → 验证 → 清理 UPDATE → 验证 NULL → re-add FK → `trans.rollback()` 还原；PostgreSQL DDL 事务化保证不污染 dev DB |
| 4 | orders 表当前 0 行，AC-3/AC-4/AC-5 测试需自造数据 | helper `_create_order` / `_create_card` 直接落库构造；每用例独立 fixture 引擎 + finally cleanup；`order_no` 与 `card_no` 用 TEST- 前缀便于兜底清理识别 |

## 4. 与计划的偏差

- 计划列出的 3 个文件（migration + model + 测试）全部按方案交付，无新增计划外源文件改动。
- 测试用例数 7（计划列 5 个 bullet 验证点 + FK/索引存在性 + migration 清理逻辑，最终拆为 7 个独立用例，覆盖更细），与计划方向一致无冲突。
- AC-7 测试设计采用"事务内复刻 upgrade + rollback"而非真实 `alembic downgrade/upgrade` 往返，避免在共享 dev DB 上反复 drop/add 全局约束影响其他连接；`alembic downgrade -1 + upgrade head` 往返已作为 AC-10 单独手动验证（见 static-verification.md 第 7 节）。

## 5. 数据兼容与迁移

- **DB 结构变更**：新增 FK `fk_orders_membership_card_id`（`ON DELETE SET NULL`）+ 新增索引 `ix_orders_membership_card_id`。
- **数据变更**：dev 库 0 条孤立被防御性清理（受影响 0 行）；生产若有孤立也将被置 NULL（语义为"无关联卡"）。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。
- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变 → 无需 `pnpm gen:types`，前端 4 端无影响。
- migration 可逆（`downgrade` drop index + drop FK；不恢复孤立数据，见 UNKNOWN U5）。

## 6. 测试结果

- `test_order_fk_membership_card.py`：**7 passed**（0.34s）
- 回归 `test_booking_fk_membership_card.py`（F4.1）：**6 passed**（0.32s）
- migration 可逆性（`alembic downgrade -1` + `alembic upgrade head`）：往返成功，孤立=0，FK + 索引恢复。
- py_compile（model + migration + test）：`COMPILE_OK_ALL`。
- `alembic heads`：单 head `f42cd3e4f5a6`（无分叉）。
- app import 冒烟：`from app.main import app` 成功，`Order.membership_card_id.foreign_keys` 含 `membership_cards.id`。

详见 [runtime-test-report.md](./runtime-test-report.md) 与 [static-verification.md](./static-verification.md)。
