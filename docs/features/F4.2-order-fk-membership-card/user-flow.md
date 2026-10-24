# F4.2 — 恢复 orders.membership_card_id 外键 + 索引 · 用户流程

> 视角：本 Feature 为纯数据库结构变更，无 HTTP 用户交互流程。以下描述"DB 层外键约束 + 索引 + migration 清理"在各场景下的行为，供验收与回归参考。
> 业务身份链路（`current_user` / `tenant_id`）不在本 Feature 范围；FK 在 DB 层对所有写入路径一视同仁。

---

## 流程 1：正常创建 order 引用存在的会员卡（DB 层放行）

1. 业务层（未来支付/购卡流程，当前未实现）创建 `Order(membership_card_id=<存在的卡 id>, ...)`。
2. `INSERT INTO orders ...` 经 FK 校验：`membership_card_id` 在 `membership_cards.id` 中存在 → 放行。
3. `db.commit()` → order 落库，`membership_card_id` 保持指向该卡。

**异常**：业务层传入的 `membership_card_id` 为 NULL（无关联卡订单）→ FK 不校验 NULL（`ON DELETE SET NULL` 列允许 NULL）→ 放行。

## 流程 2：创建 order 引用不存在的会员卡（DB 层拒绝，AC-4）

1. 业务层（或脏数据）尝试 `INSERT INTO orders ... membership_card_id=999999999`（不存在）。
2. FK 校验：`999999999 NOT IN membership_cards.id` → `IntegrityError`（`foreign key constraint "fk_orders_membership_card_id" violates`）。
3. 事务回滚，order 未落库。
4. 不会出现"指向不存在卡"的脏数据。

## 流程 3：删除会员卡 → 关联 order 置 NULL（ON DELETE SET NULL，AC-5）

1. card=100 被 1 个 order（id=1）引用（`membership_card_id=100`）。
2. `DELETE FROM membership_cards WHERE id=100`。
3. FK 触发 `ON DELETE SET NULL`：`UPDATE orders SET membership_card_id=NULL WHERE membership_card_id=100`。
   - PG 触发器按索引 `ix_orders_membership_card_id` 定位引用行（无需全表扫描）。
4. 结果：order id=1 仍存在，`membership_card_id=NULL`。
5. 后续 `payment/service.py` L61 `if order.item_type == "card" and order.membership_card_id:` 短路 → 不进入日志分支，与"无关联卡订单"行为一致。

## 流程 4：migration 清理孤立数据（AC-6 / AC-7）

**upgrade 前（dev 库 0 条孤立，生产可能非 0）**
```
orders: 0 行（dev 库）
孤立: 0 行
FK fk_orders_membership_card_id: 不存在
Index ix_orders_membership_card_id: 不存在
```

**upgrade 执行（同一事务）**
1. `UPDATE orders SET membership_card_id = NULL WHERE membership_card_id IS NOT NULL AND membership_card_id NOT IN (SELECT id FROM membership_cards)` → 0 行受影响（dev 库；生产可能 N 行）。
2. `ALTER TABLE orders ADD CONSTRAINT fk_orders_membership_card_id FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id) ON DELETE SET NULL` → 此时无孤立，加约束成功。
3. `CREATE INDEX ix_orders_membership_card_id ON orders USING btree (membership_card_id)` → 索引建立。
4. `COMMIT` → alembic_version = `f42cd3e4f5a6`。

**upgrade 后**
```
orders: 0 行（不变）
孤立: 0 行
FK fk_orders_membership_card_id: 存在，ON DELETE SET NULL
Index ix_orders_membership_card_id: 存在
```

**downgrade（回滚）**
1. `DROP INDEX ix_orders_membership_card_id` → 索引移除。
2. `ALTER TABLE orders DROP CONSTRAINT fk_orders_membership_card_id` → FK 移除。
3. 不恢复孤立数据（原始指向的卡本不存在，无可恢复信息）。
4. `COMMIT` → alembic_version = `f41ab2c3d4e5`。

## 流程 5：跨层调用链（不变）

```
Service（不变，order 模块当前仅有 models.py）/ payment Service（不变，只读）
  → Repository（不变，order 模块当前无 repository.py）
  → SQLAlchemy → PostgreSQL（新增 FK 约束 + 索引）
```

- Service / Repository / Router / schemas 代码零改动：FK 约束 + 索引在 DB 层，对 ORM `INSERT`/`DELETE` 透明。
- `payment/service.py` 既有 `if order.item_type == "card" and order.membership_card_id:` 日志逻辑不变；它在 `membership_card_id IS NULL` 时已正确短路。
- 租户隔离：FK 约束是跨租户的引用完整性（`membership_cards.id` 全局唯一主键），不影响 `TenantAwareRepository` 的 `tenant_id` 过滤语义。
- 索引 `ix_orders_membership_card_id` 不含 `tenant_id` 前缀：该索引用于 FK 触发的 `UPDATE orders SET membership_card_id=NULL WHERE membership_card_id=<x>` 行定位（PG 触发器不经过租户过滤），以及未来按卡反查订单；按租户列表查询仍走既有 `idx_orders_user` / `idx_orders_status_created` 复合索引。

## 流程 6：回归场景（FK + 索引不破坏既有行为）

- F4.1（bookings FK）：`bookings.membership_card_id` FK 与 `orders.membership_card_id` FK 相互独立，本 Feature 不动 bookings 表 → 无影响。
- 支付服务（payment/service.py）：仅读 `order.membership_card_id`，FK 与索引对读取透明 → 无影响。
- 租户隔离 / RBAC / 认证：均不涉及 orders 表结构变更 → 无影响。
