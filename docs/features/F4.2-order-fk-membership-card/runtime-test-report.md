# F4.2 — 运行时测试报告

> 日期：2026-09-29
> 环境：本地开发机，PostgreSQL（Docker 共享开发库，预置种子租户 dance-school），Redis 可用。migration `f42cd3e4f5a6` 已 apply（alembic_version=f42cd3e4f5a6）。

## 1. 测试入口

```bash
# 主测试（F4.2）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_order_fk_membership_card.py -v

# 回归（AC-8，F4.1 不被破坏）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_fk_membership_card.py -v
```

## 2. 结果摘要

| 套件 | 结果 |
|------|------|
| `test_order_fk_membership_card.py` | **7 passed**（0.34s） |
| `test_booking_fk_membership_card.py`（F4.1 回归） | **6 passed**（0.32s） |
| **合计** | **13 passed, 2 warnings** |

warnings 均为既有第三方库 deprecation（passlib `crypt`、FastAPI `example`），与本 Feature 无关。

## 3. 用例明细（test_order_fk_membership_card.py，7/7 通过）

### 3.1 TestOrderFkMembershipCard（FK + 索引行为验证，6/6）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_fk_constraint_exists_with_on_delete_set_null` | AC-1 | 查询 `pg_constraint` 取 `fk_orders_membership_card_id` 的 `pg_get_constraintdef`；定义含 `FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id)` 与 `ON DELETE SET NULL` |
| `test_index_on_membership_card_id_exists` | AC-2 | 查询 `pg_indexes` for `orders`；`indexdef` 含 `CREATE INDEX`、`ix_orders_membership_card_id`、`membership_card_id` |
| `test_order_with_valid_membership_card_succeeds` | AC-3 | 落库 1 ACTIVE card + 1 order（card_id 指向该卡）；不抛异常；重读 order `membership_card_id == card_id` |
| `test_order_with_nonexistent_card_raises_integrity_error` | AC-4 | `session.add(Order(membership_card_id=999999999))` + `commit` → `pytest.raises(IntegrityError)`；重查 `membership_card_id=999999999` 的 order 为空（未落库） |
| `test_delete_card_sets_order_card_id_null` | AC-5 | 落库 card + order（引用该卡）；`DELETE FROM membership_cards WHERE id=card_id`；重读 order 仍存在且 `membership_card_id is None`（ON DELETE SET NULL） |
| `test_no_orphan_orders_after_migration` | AC-6 | `SELECT COUNT(*) ... LEFT JOIN membership_cards ... WHERE membership_card_id IS NOT NULL AND m.id IS NULL` → `== 0` |

### 3.2 TestOrderFkMigrationLogic（migration 清理逻辑，1/1）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_migration_cleanup_clears_orphan_and_readds_fk` | AC-7 | 显式事务内：drop FK → 插孤立 order（card_id=999999999，item_type='card'，item_id=1，amount=99.00，status=PENDING）→ 验证孤立存在 → 执行清理 UPDATE → 验证 card_id 变 NULL → re-add FK 成功 → `trans.rollback()` 还原；二次确认 dev DB 无残留测试 order |

## 4. 测试可信度分析

### 4.1 测试逻辑的区分力

- **migration 未应用前**：`test_fk_constraint_exists_with_on_delete_set_null` 查不到 FK → 失败；`test_index_on_membership_card_id_exists` 查不到索引 → 失败；`test_order_with_nonexistent_card_raises_integrity_error` 插入 card_id=999999999 不抛 IntegrityError（无 FK） → 失败。
- **migration 应用后**：上述 3 用例全部通过 → 证明 FK 已建 + 索引已建。
- 若回退本 Feature（drop FK + drop index），`test_fk_constraint_exists_with_on_delete_set_null` / `test_index_on_membership_card_id_exists` / `test_order_with_nonexistent_card_raises_integrity_error` 必失败。

### 4.2 真实 DB 事务性保障

- AC-3/AC-4/AC-5：用独立 `AsyncSession` 落库 + commit，再用新 session 读 DB 验证终态（避免读到 dirty session）。
- AC-4 的 `IntegrityError` 由 PostgreSQL FK 校验在 commit 时抛出（asyncpg → SQLAlchemy），非 mock。
- AC-5 的 `ON DELETE SET NULL` 由 PostgreSQL FK 触发器在 `DELETE FROM membership_cards` 时执行 `UPDATE orders`，跨连接生效；PG 触发器按索引 `ix_orders_membership_card_id` 定位引用行。

### 4.3 AC-7 的事务隔离设计

- 用 `engine.connect()` + `conn.begin()` 显式事务，所有 DDL（DROP/ADD CONSTRAINT）+ DML（INSERT/UPDATE）在同一事务内。
- PostgreSQL DDL 事务化：事务未 commit 前，并发连接看到旧状态（FK 仍在），仅本事务内可见 drop；`trans.rollback()` 还原，dev DB 无残留。
- 二次确认：rollback 后 `SELECT * FROM orders WHERE id=<测试 order_id>` 为空（INSERT 被回滚）。
- 索引不阻塞孤立插入，故 AC-7 不动索引（仅 drop/re-add FK）；re-add FK 在清理 UPDATE 后成功（无孤立）。

### 4.4 事件循环隔离（借鉴 F4.1 / F2.4）

- `shared_data`（session-scoped）在 session loop 内创建并 dispose engine，只返回纯数据 dict。
- `local_db`（function-scoped）为每用例独立 engine + session_factory。
- AC-7 用独立 `create_async_engine` 在用例内完成，结束后 `engine.dispose()`。

7/7 全绿，无跨 loop 错误。

## 5. 回归结论

- `test_booking_fk_membership_card.py`（F4.1，6/6）全部通过 → **AC-8 满足**。
- F4.1 bookings FK 行为未受本 Feature 影响：本 Feature 不动 bookings 表，orders 与 bookings 表相互独立。
- 本 Feature 仅在 DB 层加 FK + 索引 + 防御性清理孤立，Service/Repository 零改动 → 业务逻辑零回归风险。
- 关键：`payment/service.py` L61 `if order.item_type == "card" and order.membership_card_id:` 短路模式在孤立被置 NULL 后仍正确工作（这些 order 指向的卡本不存在，置 NULL 后跳过日志分支，与"无关联卡订单"一致）。

## 6. 性能与资源

- 7 个主测试用例约 0.34s（含 fixture 一次性解析种子 IDs + 每用例独立 card/order 创建/清理）。
- `ON DELETE SET NULL` 触发时按 `ix_orders_membership_card_id` 索引定位引用行：orders 量级小（dev 库 0 行），索引收益在生产高量级时体现。
- 全部 13 用例（含回归）约 0.66s（0.34s + 0.32s），无慢查询告警。

## 7. 迭代记录

| 轮次 | 问题 | 修复 |
|------|------|------|
| 第 1 轮 | — | **7/7 通过**（首版即全绿，无迭代） |
