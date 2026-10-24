# F4.1 — Review

> 日期：2026-09-29 ｜ 审查人：database-engineer（自审 + 规则清单）

## Scope

- 变更严格限于 Feature 定义：
  1. 新建 migration `f41ab2c3d4e5_restore_bookings_membership_card_fk.py`（清理孤立 UPDATE + `create_foreign_key` ON DELETE SET NULL；downgrade `drop_constraint`）。
  2. `booking/models.py` `membership_card_id` 列补 `ForeignKey("membership_cards.id", ondelete="SET NULL")`。
  3. 新增测试 `test_booking_fk_membership_card.py`（6 用例）。
- Service / Repository / Router / schemas / OpenAPI / 前端 / MCP **均未改动**。
- 未引入新依赖、未改 OpenAPI 路径/方法/请求体/响应模型、未改 Redis。

## Architecture

- 分层合规：FK 约束在 DB 层（migration），对 Service/Repository 透明；Service/Repository 零改动。
- migration 走 Alembic `op.create_foreign_key` / `op.drop_constraint`，非手写 SQL 脚本；清理用 `op.execute(sa.text(...))` 是结构变更清理（非业务读写）。
- 事务边界：清理 UPDATE + ADD CONSTRAINT 在同一 migration upgrade（alembic `Will assume transactional DDL`），原子完成。
- 租户隔离：FK 是跨租户引用完整性（`membership_cards.id` 全局主键）；`TenantAwareRepository` 的 `tenant_id` 过滤语义不变。
- 与 init migration 原设计一致（`4bd04b738098` 原本 `ondelete="SET NULL"`），属"恢复"而非"新增设计"。

## Code

- migration：`revision=f41ab2c3d4e5` / `down_revision=211f847af16c`；约束名显式 `fk_bookings_membership_card_id`（便于 downgrade 精确 drop）；清理 SQL `WHERE membership_card_id IS NOT NULL AND membership_card_id NOT IN (SELECT id FROM membership_cards)` 正确处理 NULL。
- 模型：`ForeignKey` 已在第 5 行 import；`mapped_column(BigInteger, ForeignKey("membership_cards.id", ondelete="SET NULL"), nullable=True)` 与 migration `ondelete="SET NULL"` 完全一致。
- downgrade：仅 `drop_constraint`；不恢复孤立数据（不可能，原始指向的卡本不存在，见 UNKNOWN U3）。

## Security

- 无端点变更；`@require_permissions` / `get_current_user` 未动。
- 租户隔离：FK 不影响 `tenant_id` 过滤；`membership_cards.id` 全局唯一主键，跨租户引用完整性正确。
- DB 层 FK 为最后兜底：业务层 Service 在创建 booking 前已校验 card 有效性；即便 FK 触发 `IntegrityError`，经全局异常处理器返回统一信封，不回显 SQL/traceback。
- migration 内 SQL 不含敏感信息；约束名稳定可审计。

## Transaction / Concurrency

- **核心修复**：恢复 DB 层引用完整性，消除"插入指向不存在卡的 booking"的风险。
  - 修复前：`membership_card_id` 无 FK，DB 无法阻止孤立引用（实测 4 条孤立）。
  - 修复后：FK `ON DELETE SET NULL` 在 DB 层强制 `membership_card_id` 必须指向存在的卡（或 NULL）。
- 清理 + 建 FK 原子事务：alembic `Will assume transactional DDL` → UPDATE + ALTER 在一个事务内，若清理失败则 FK 不加，DB 维持原状，不会出现"清理了但没加约束"的中间态。
- `ON DELETE SET NULL`：删 card 时 PG 触发 `UPDATE bookings SET membership_card_id=NULL WHERE membership_card_id=<card_id>`；业务层 `if booking.membership_card_id:` 短路 → 置 NULL 安全（预约本身保留，取消时不触发 restore_credit）。
- 并发风险：upgrade 前 DB 无 FK，并发写入仍可产生新孤立（生产灰度建议维护窗口或先停写）；dev 库已验证无此问题。AC-6 测试在显式事务内 drop/re-add FK，PostgreSQL DDL 事务化保证并发连接不受影响。

## Migration

- revision 链：`down_revision=211f847af16c`（本 Feature 前唯一 head）；应用后 `alembic heads` 仍单 head `f41ab2c3d4e5`，无分叉。
- 可逆性（AC-9 手动验证）：`alembic downgrade -1` → FK 消失、alembic_version=211f847af16c；`alembic upgrade head` → FK 恢复、alembic_version=f41ab2c3d4e5、孤立=0。往返成功。
- 数据变更：4 条孤立 `membership_card_id` 由不存在卡 ID 置 NULL（语义为"无关联卡"，业务层已正确处理 NULL）。
- downgrade 不恢复孤立数据（不可能，见 UNKNOWN U3）。

## Regression

- `test_cancel_schedule_rollback.py`（12/12）+ `test_booking_ownership.py`（10/10）+ `test_checkin_complete_lock.py`（9/9）：**31/31 通过** → AC-7 满足。
- 取消排期回补课时（F2.4）、预约归属（F2.2）、签到/完成行锁（F2.3）行为未受影响。
- 本 Feature 仅 DB 层加 FK + 清理孤立，Service/Repository 零改动 → 业务逻辑零回归风险。

## Acceptance

- AC-1（FK 存在）：`test_fk_constraint_exists_with_on_delete_set_null` 通过。
- AC-2（正常引用）：`test_booking_with_valid_membership_card_succeeds` 通过。
- AC-3（IntegrityError）：`test_booking_with_nonexistent_card_raises_integrity_error` 通过。
- AC-4（ON DELETE SET NULL）：`test_delete_card_sets_booking_card_id_null` 通过。
- AC-5（孤立=0）：`test_no_orphan_bookings_after_migration` 通过。
- AC-6（migration 清理逻辑）：`test_migration_cleanup_clears_orphan_and_readds_fk` 通过。
- AC-7（回归）：31/31 通过。
- AC-8（分层合规）：静态 grep 验证 Service/Repository 零改动、模型与 migration FK 一致（详见 [static-verification.md](./static-verification.md)）。
- AC-9（可逆）：`alembic downgrade -1` + `alembic upgrade head` 往返成功。

## 遗留事项（不阻塞）

1. `bookings.membership_card_id` 无索引：`ON DELETE SET NULL` 时按该列定位引用行，当前 bookings 量级小可接受；高量级时建议加索引（属另一 Feature 范围，本 Feature 不扩大 scope）。
2. 生产灰度并发风险：upgrade 前 DB 无 FK，并发写入仍可产生新孤立；建议生产在维护窗口或先停写再 upgrade（dev 库已验证无此问题）。
3. `orders.membership_card_id` 仍无 FK（F4.2 范围），本 Feature 不处理。

## 结论

**READY_FOR_ACCEPTANCE**
