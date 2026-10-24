# F4.1 — 恢复 bookings.membership_card_id 外键 · 验收标准

> 每条 AC 均可通过集成测试（`tests/integration/test_booking_fk_membership_card.py`）验证。
> 测试入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_fk_membership_card.py -v`

| # | AC | 验证方式 | 预期 |
|---|----|---------|------|
| AC-1 | FK 约束存在且 `ON DELETE SET NULL` | IT：查询 `pg_constraint`，取 `fk_bookings_membership_card_id` 的 `pg_get_constraintdef(oid)` | 定义含 `FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id)` 与 `ON DELETE SET NULL` |
| AC-2 | 正常 booking 引用存在的卡 → 成功 | IT：落库 1 schedule + 1 ACTIVE card + 1 BOOKED booking（card_id 指向该卡） | 不抛异常；重读 booking `membership_card_id == card_id` |
| AC-3 | booking 引用不存在的 card_id → IntegrityError | IT：落库 1 schedule；`session.add(Booking(membership_card_id=999999999))` + `commit` | `pytest.raises(IntegrityError)`；重查 `membership_card_id=999999999` 的 booking 为空（未落库） |
| AC-4 | 删除 card → booking.membership_card_id 变 NULL | IT：落库 schedule + card + booking（引用该卡）；`DELETE FROM membership_cards WHERE id=card_id` | booking 仍存在；重读 `membership_card_id is None`（ON DELETE SET NULL 生效） |
| AC-5 | migration 已清理孤立数据 | IT：`SELECT COUNT(*) FROM bookings b LEFT JOIN membership_cards m ON b.membership_card_id=m.id WHERE b.membership_card_id IS NOT NULL AND m.id IS NULL` | `== 0`（migration 前 4，migration 后 0） |
| AC-6 | migration 清理逻辑本身正确 | IT：在显式事务内复刻 upgrade：drop FK → 插孤立 booking（card_id=999999999）→ 验证孤立存在 → 执行清理 UPDATE → 验证 card_id 变 NULL → re-add FK 成功；最终 `trans.rollback()` | 清理 UPDATE 后孤立 card_id 由 999999999 变 NULL；re-add FK 不抛异常；回滚后 dev DB 无残留测试 booking |
| AC-7 | 回归不破现有行为 | 回归：`test_cancel_schedule_rollback.py` + `test_booking_ownership.py` + `test_checkin_complete_lock.py` | 全部通过（cancel_rollback 12 + booking_ownership 10 + checkin_lock 9 = 31） |
| AC-8 | 分层合规 | 静态：FK 约束在 DB 层（migration）；Service/Repository 零改动；模型与 migration 一致 | 无违规 |
| AC-9 | migration 可逆 | `alembic downgrade -1` → FK 消失、alembic_version=211f847af16c；`alembic upgrade head` → FK 恢复、alembic_version=f41ab2c3d4e5、孤立=0 | 往返成功 |

## 辅助断言

- AC-1a：`pg_constraint` 中 `fk_bookings_membership_card_id` 的 `contype='f'`（外键）。
- AC-3a：`IntegrityError` 由 SQLAlchemy 抛出（DB 层 FK 违反），非业务层手写校验。
- AC-6a：回滚后 `SELECT * FROM bookings WHERE id=<测试 booking_id>` 为空（事务回滚还原 dev DB）。

## HTTP 状态码与信封约定（对照 contracts.md）

- 本 Feature 无 HTTP 端点变更，无新增信封/状态码。
- `IntegrityError` 不会直接透传给前端：业务层 Service 在创建 booking 前已校验 card 有效性（既有逻辑），DB 层 FK 为最后兜底；即便触发，经全局异常处理器返回统一信封，不回显 SQL/traceback。
