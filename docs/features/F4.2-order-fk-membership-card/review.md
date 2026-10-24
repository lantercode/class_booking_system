# F4.2 — Review

> 日期：2026-09-29 ｜ 审查人：database-engineer（自审 + 规则清单）

## Scope

- 变更严格限于 Feature 定义：
  1. 新建 migration `f42cd3e4f5a6_restore_orders_membership_card_fk_and_index.py`（清理孤立 UPDATE + `create_foreign_key` ON DELETE SET NULL + `create_index`；downgrade `drop_index` + `drop_constraint`）。
  2. `order/models.py` `membership_card_id` 列补 `ForeignKey("membership_cards.id", ondelete="SET NULL")`；`__table_args__` 补 `Index("ix_orders_membership_card_id", "membership_card_id")`。
  3. 新增测试 `test_order_fk_membership_card.py`（7 用例）。
- Service / Repository / Router / schemas / OpenAPI / 前端 / MCP / payment service **均未改动**。
- 未引入新依赖、未改 OpenAPI 路径/方法/请求体/响应模型、未改 Redis。

## Architecture

- 分层合规：FK + 索引在 DB 层（migration），对 Service/Repository 透明；Service/Repository 零改动（order 模块当前仅有 models.py）。
- migration 走 Alembic `op.create_foreign_key` / `op.create_index` / `op.drop_index` / `op.drop_constraint`，非手写 SQL 脚本；清理用 `op.execute(sa.text(...))` 是结构变更清理（非业务读写）。
- 事务边界：清理 UPDATE + ADD CONSTRAINT + CREATE INDEX 在同一 migration upgrade（alembic `Will assume transactional DDL`），原子完成。
- 租户隔离：FK 是跨租户引用完整性（`membership_cards.id` 全局主键）；索引不含 `tenant_id` 前缀（用于 FK 触发器行定位 + 按卡反查）；`TenantAwareRepository` 的 `tenant_id` 过滤语义不变。
- 与 F4.1 同范式（清理 UPDATE + create_foreign_key SET NULL），并扩展加索引（Task T4.2.2 要求）。

## Code

- migration：`revision=f42cd3e4f5a6` / `down_revision=f41ab2c3d4e5`；约束名显式 `fk_orders_membership_card_id`、索引名显式 `ix_orders_membership_card_id`（便于 downgrade 精确 drop）；清理 SQL `WHERE membership_card_id IS NOT NULL AND membership_card_id NOT IN (SELECT id FROM membership_cards)` 正确处理 NULL。
- 模型：`ForeignKey` 与 `Index` 已在文件顶部 import（L8-9）；`mapped_column(BigInteger, ForeignKey("membership_cards.id", ondelete="SET NULL"), nullable=True, ...)` 与 migration `ondelete="SET NULL"` 完全一致；`__table_args__` 新增 `Index("ix_orders_membership_card_id", "membership_card_id")` 与 migration `create_index` 一致。
- downgrade：先 `drop_index` 再 `drop_constraint`（与 upgrade 反序，更安全可审计）；不恢复孤立数据（不可能，原始指向的卡本不存在，见 UNKNOWN U5）。

## Security

- 无端点变更；`@require_permissions` / `get_current_user` 未动。
- 租户隔离：FK 不影响 `tenant_id` 过滤；`membership_cards.id` 全局唯一主键，跨租户引用完整性正确；索引不含 tenant_id 前缀不影响租户过滤语义（按租户列表查询走既有 `idx_orders_user` / `idx_orders_status_created` 复合索引）。
- DB 层 FK 为最后兜底：order 模块当前无 Service（无 ORM 创建 Order 路径）；即便未来支付流程创建 Order 时 FK 触发 `IntegrityError`，经全局异常处理器返回统一信封，不回显 SQL/traceback。
- migration 内 SQL 不含敏感信息；约束名 / 索引名稳定可审计。

## Transaction / Concurrency

- **核心修复**：恢复 DB 层引用完整性 + 加索引支撑 `ON DELETE SET NULL` 行定位与按卡反查。
  - 修复前：`membership_card_id` 无 FK 无索引，DB 无法阻止孤立引用，`ON DELETE SET NULL` 时无索引支撑。
  - 修复后：FK `ON DELETE SET NULL` 在 DB 层强制 `membership_card_id` 必须指向存在的卡（或 NULL）；索引 `ix_orders_membership_card_id` 加速 FK 触发器行定位。
- 清理 + 建 FK + 建索引原子事务：alembic `Will assume transactional DDL` → UPDATE + ALTER + CREATE INDEX 在一个事务内，若清理失败则 FK 与索引不加，DB 维持原状，不会出现"清理了但没加约束/索引"的中间态。
- `ON DELETE SET NULL`：删 card 时 PG 触发 `UPDATE orders SET membership_card_id=NULL WHERE membership_card_id=<card_id>`；PG 触发器按索引 `ix_orders_membership_card_id` 定位引用行；业务层 `payment/service.py` L61 `if order.membership_card_id:` 短路 → 置 NULL 安全（订单本身保留）。
- 并发风险：upgrade 前 DB 无 FK，并发写入仍可产生新孤立（生产灰度建议维护窗口或先停写）；dev 库已验证无此问题。AC-7 测试在显式事务内 drop/re-add FK，PostgreSQL DDL 事务化保证并发连接不受影响。

## Migration

- revision 链：`down_revision=f41ab2c3d4e5`（F4.1 后唯一 head）；应用后 `alembic heads` 仍单 head `f42cd3e4f5a6`，无分叉。
- 可逆性（AC-10 手动验证）：`alembic downgrade -1` → FK + 索引消失、alembic_version=f41ab2c3d4e5；`alembic upgrade head` → FK + 索引恢复、alembic_version=f42cd3e4f5a6、孤立=0。往返成功。
- 数据变更：dev 库 0 条孤立被防御性清理（受影响 0 行）；生产若有孤立也将被置 NULL（语义为"无关联卡"，业务层已正确处理 NULL）。
- downgrade 不恢复孤立数据（不可能，见 UNKNOWN U5）。

## Regression

- `test_booking_fk_membership_card.py`（F4.1，6/6）：**6/6 通过** → AC-8 满足。
- F4.1 bookings FK 行为未受本 Feature 影响：本 Feature 不动 bookings 表，orders 与 bookings 表相互独立。
- 本 Feature 仅 DB 层加 FK + 索引 + 防御性清理孤立，Service/Repository 零改动 → 业务逻辑零回归风险。

## Acceptance

- AC-1（FK 存在）：`test_fk_constraint_exists_with_on_delete_set_null` 通过。
- AC-2（索引存在）：`test_index_on_membership_card_id_exists` 通过。
- AC-3（正常引用）：`test_order_with_valid_membership_card_succeeds` 通过。
- AC-4（IntegrityError）：`test_order_with_nonexistent_card_raises_integrity_error` 通过。
- AC-5（ON DELETE SET NULL）：`test_delete_card_sets_order_card_id_null` 通过。
- AC-6（孤立=0）：`test_no_orphan_orders_after_migration` 通过。
- AC-7（migration 清理逻辑）：`test_migration_cleanup_clears_orphan_and_readds_fk` 通过。
- AC-8（回归）：F4.1 6/6 通过。
- AC-9（分层合规）：静态 grep 验证 Service/Repository 零改动、模型与 migration FK + Index 一致（详见 [static-verification.md](./static-verification.md)）。
- AC-10（可逆）：`alembic downgrade -1` + `alembic upgrade head` 往返成功。

## 遗留事项（不阻塞）

1. 生产灰度并发风险：upgrade 前 DB 无 FK，并发写入仍可产生新孤立；建议生产在维护窗口或先停写再 upgrade（dev 库已验证无此问题）。
2. `bookings.membership_card_id` 仍无索引（F4.1 D7 评估量级小未加；本 Feature 不扩大到 bookings；如未来 bookings 量级增长可另立 Feature 加索引）。
3. order 模块当前仅有 models.py（无 service/router/repository），未来实现支付/购卡流程时创建 Order 的路径需经全局异常处理器捕获 `IntegrityError` 返回统一信封。

## 结论

**READY_FOR_ACCEPTANCE**
