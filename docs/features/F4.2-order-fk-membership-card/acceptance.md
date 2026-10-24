# F4.2 — 恢复 orders.membership_card_id 外键 + 索引 · 验收标准

> 每条 AC 均可通过集成测试（`tests/integration/test_order_fk_membership_card.py`）验证。
> 测试入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_order_fk_membership_card.py -v`

| # | AC | 验证方式 | 预期 |
|---|----|---------|------|
| AC-1 | FK 约束存在且 `ON DELETE SET NULL` | IT：查询 `pg_constraint`，取 `fk_orders_membership_card_id` 的 `pg_get_constraintdef(oid)` | 定义含 `FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id)` 与 `ON DELETE SET NULL` |
| AC-2 | 索引 `ix_orders_membership_card_id` 存在 | IT：查询 `pg_indexes` for `orders` | `indexdef` 含 `CREATE INDEX ix_orders_membership_card_id ON orders USING btree (membership_card_id)` |
| AC-3 | 正常 order 引用存在的卡 → 成功 | IT：落库 1 ACTIVE card + 1 order（card_id 指向该卡） | 不抛异常；重读 order `membership_card_id == card_id` |
| AC-4 | order 引用不存在的 card_id → IntegrityError | IT：`session.add(Order(membership_card_id=999999999))` + `commit` | `pytest.raises(IntegrityError)`；重查 `membership_card_id=999999999` 的 order 为空（未落库） |
| AC-5 | 删除 card → order.membership_card_id 变 NULL | IT：落库 card + order（引用该卡）；`DELETE FROM membership_cards WHERE id=card_id` | order 仍存在；重读 `membership_card_id is None`（ON DELETE SET NULL 生效） |
| AC-6 | migration 已清理孤立数据 | IT：`SELECT COUNT(*) FROM orders o LEFT JOIN membership_cards m ON o.membership_card_id=m.id WHERE o.membership_card_id IS NOT NULL AND m.id IS NULL` | `== 0` |
| AC-7 | migration 清理逻辑本身正确 | IT：在显式事务内复刻 upgrade：drop FK → 插孤立 order（card_id=999999999）→ 验证孤立存在 → 执行清理 UPDATE → 验证 card_id 变 NULL → re-add FK 成功；最终 `trans.rollback()` | 清理 UPDATE 后孤立 card_id 由 999999999 变 NULL；re-add FK 不抛异常；回滚后 dev DB 无残留测试 order |
| AC-8 | 回归不破现有行为 | 回归：`test_booking_fk_membership_card.py`（F4.1） | 全部通过（6/6） |
| AC-9 | 分层合规 | 静态：FK + 索引在 DB 层（migration）；Service/Repository 零改动；模型与 migration 一致 | 无违规 |
| AC-10 | migration 可逆 | `alembic downgrade -1` → FK + 索引消失、alembic_version=f41ab2c3d4e5；`alembic upgrade head` → FK + 索引恢复、alembic_version=f42cd3e4f5a6 | 往返成功 |

## 辅助断言

- AC-1a：`pg_constraint` 中 `fk_orders_membership_card_id` 的 `contype='f'`（外键）。
- AC-2a：`ix_orders_membership_card_id` 的 `indexdef` 含 `btree`（非其他索引类型）。
- AC-4a：`IntegrityError` 由 SQLAlchemy 抛出（DB 层 FK 违反），非业务层手写校验。
- AC-7a：回滚后 `SELECT * FROM orders WHERE id=<测试 order_id>` 为空（事务回滚还原 dev DB）。

## HTTP 状态码与信封约定（对照 contracts.md）

- 本 Feature 无 HTTP 端点变更，无新增信封/状态码。
- `IntegrityError` 不会直接透传给前端：当前 order 模块仅有 models.py（无 router/service）；即便未来支付流程创建 Order 时触发 FK 违反，经全局异常处理器返回统一信封，不回显 SQL/traceback。
