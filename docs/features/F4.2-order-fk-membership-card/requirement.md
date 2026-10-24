# F4.2 — 恢复 orders.membership_card_id 外键 + 索引 · 需求文档

> Feature ID：F4.2
> 作者：database-engineer
> 日期：2026-09-29
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（纯数据库结构任务，单领域轨道，不召前端/后端业务层；不动 Service/Repository 逻辑）
> 依赖：无新外部依赖；复用既有 `membership_cards` 表（主键 `id BigInteger`）
> 前置 Feature：F4.1（bookings.membership_card_id 外键，已完成；当前 alembic head = `f41ab2c3d4e5`）

---

## Goal

订单必须引用存在的会员卡，且 `orders.membership_card_id` 列在按卡查询 / `ON DELETE SET NULL` 行定位时有索引支撑。`orders.membership_card_id` 当前只是一列 `BigInteger`，没有外键约束也没有索引——DB 无法阻止插入指向不存在 `membership_cards.id` 的引用（dev 库当前 0 条孤立，但生产可能存在）。

修复目标：用一条 Alembic migration 在同一事务内先清理孤立引用（防御性清理，把指向不存在卡的 `membership_card_id` 置 NULL），再重建外键 `fk_orders_membership_card_id`（`ON DELETE SET NULL`），并新增索引 `ix_orders_membership_card_id`；在 ORM 模型层补回 `ForeignKey("membership_cards.id", ondelete="SET NULL")` 与 `Index("ix_orders_membership_card_id", "membership_card_id")` 使模型与 DB 一致。

## User Story

作为系统，
我希望 `orders.membership_card_id` 在数据库层有外键约束（`ON DELETE SET NULL`），以便：
- DB 直接拒绝插入指向不存在会员卡的订单，不再依赖应用层兜底。
- 会员卡被删除时，关联订单的 `membership_card_id` 自动置 NULL（订单本身保留；`payment/service.py` 当前仅以 `if order.item_type == "card" and order.membership_card_id:` 做日志判断，置 NULL 后语义为"无关联卡"，安全）。

作为运维，
我希望 `orders.membership_card_id` 上有索引 `ix_orders_membership_card_id`，以便：
- `ON DELETE SET NULL` 时 PG 触发器按该列定位引用行不必全表扫描；
- 未来按卡反查订单（如对账、退卡关联订单查询）有索引支撑。

作为运维，
我希望 migration 有完整 upgrade + downgrade 且 revision 链正确（`down_revision=f41ab2c3d4e5` F4.1 后唯一 head），以便生产灰度与回滚可审计。

## Background / 现状（已核查的代码与 DB 事实）

| 事实 | 证据 |
|------|------|
| `Order.membership_card_id` 当前只有 `BigInteger` 无 FK | [models.py:58-63](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/order/models.py#L58-63)（修复前）：`membership_card_id: Mapped[int \| None] = mapped_column(BigInteger, nullable=True, comment="关联会员卡ID（购买次卡时生成）")` |
| 该列由 `57aeb9dcf020` migration 新增但只落库 BigInteger 无 FK | [57aeb9dcf020_add_membership_card_id_to_orders_table.py:25-33](file:///Users/lixiang/Desktop/class_booking_system/apps/api/alembic/versions/57aeb9dcf020_add_membership_card_id_to_orders_table.py#L25-33)：`op.add_column("orders", sa.Column("membership_card_id", sa.BigInteger(), nullable=True, comment="..."))` —— 仅加列 |
| orders 表当前无该 FK | 实测 `pg_constraint` for `orders`：仅 `orders_tenant_id_fkey`(CASCADE) / `orders_user_id_fkey`(RESTRICT) |
| orders 表当前无该列索引 | 实测 `pg_indexes` for `orders`：`orders_pkey` / `orders_order_no_key` / `orders_public_id_key` / `idx_orders_status_created` / `idx_orders_user` / `ix_orders_tenant_id`，无 `membership_card_id` 索引 |
| 孤立计数 = 0 | 实测：`SELECT COUNT(*) FROM orders o LEFT JOIN membership_cards m ON o.membership_card_id=m.id WHERE o.membership_card_id IS NOT NULL AND m.id IS NULL` → 0（orders 总 0 行） |
| `MembershipCard.id` 为 `BigInteger` 主键 | [membership/models.py:160](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L160)：`id: Mapped[int] = mapped_column(BigInteger, primary_key=True)` |
| 当前 alembic 唯一 head | `alembic heads` → `f41ab2c3d4e5 (head)`（F4.1 新增）；无其他 migration 以其为 `down_revision` |
| 业务层仅读不写 | `payment/service.py` L61-63 仅 `if order.item_type == "card" and order.membership_card_id:` 做日志；全仓库 grep `Order(` 仅命中模型定义本身，无任何 ORM 创建 Order 的业务路径；无裸 `INSERT INTO orders` SQL |
| 同类模式已存在 | [Booking.membership_card_id](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L52-56)：`ForeignKey("membership_cards.id", ondelete="SET NULL")`（F4.1 已恢复）；本 Feature 对 orders 做同构恢复 |

## Scope（In Scope）

1. 新增 Alembic migration `f42cd3e4f5a6_restore_orders_membership_card_fk_and_index`：
   - `down_revision = "f41ab2c3d4e5"`（F4.1 后唯一 head）。
   - `upgrade`（同一事务，原子完成）：
     1. `UPDATE orders SET membership_card_id = NULL WHERE membership_card_id IS NOT NULL AND membership_card_id NOT IN (SELECT id FROM membership_cards)` 清理孤立（防御性，dev 库当前 0 条但生产可能非 0）；
     2. `op.create_foreign_key("fk_orders_membership_card_id", "orders", "membership_cards", ["membership_card_id"], ["id"], ondelete="SET NULL")`；
     3. `op.create_index("ix_orders_membership_card_id", "orders", ["membership_card_id"])`。
   - `downgrade`：先 `op.drop_index("ix_orders_membership_card_id", "orders")` 再 `op.drop_constraint("fk_orders_membership_card_id", "orders", type_="foreignkey")`（不恢复孤立数据）。
2. `apps/api/src/app/modules/order/models.py`：
   - `membership_card_id` 列补 `ForeignKey("membership_cards.id", ondelete="SET NULL")`，与 migration 一致；
   - `__table_args__` 补 `Index("ix_orders_membership_card_id", "membership_card_id")`，与 migration 一致。
3. 新增集成测试 `apps/api/tests/integration/test_order_fk_membership_card.py`：7 用例覆盖 FK 存在性 / 索引存在性 / 正常引用 / IntegrityError / ON DELETE SET NULL / 孤立计数=0 / migration 清理逻辑本身正确。

## Out of Scope

- 不修改 Service / Repository / Router / schemas（FK 约束在 DB 层；业务层 `payment/service.py` 已 `if order.membership_card_id:` 短路，置 NULL 安全）。
- 不修改 OpenAPI 契约（无端点变更）。
- 不修改前端 4 端 / MCP。
- 不引入新依赖。
- 不处理 `bookings.membership_card_id`（F4.1 范围，已完成；F4.1 评估时 bookings 量级小未加索引，本 Feature 不扩大到 bookings）。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1：FK `fk_orders_membership_card_id` 存在且 `ON DELETE SET NULL`。
- AC-2：索引 `ix_orders_membership_card_id` 存在。
- AC-3：创建 order 引用存在的卡 → 成功，`membership_card_id` 落库。
- AC-4：创建 order 引用不存在的 `card_id` → `IntegrityError`（FK 校验生效）。
- AC-5：删除 card → 关联 order 的 `membership_card_id` 变 NULL（`ON DELETE SET NULL`）。
- AC-6：migration 已清理孤立数据（孤立计数 == 0）。
- AC-7：migration 清理逻辑本身正确（事务内复刻：drop FK → 插孤立 → 清理 UPDATE → `card_id` 变 NULL → re-add FK 成功；整体回滚不污染 dev DB）。

## Dependencies

- 复用：既有 `membership_cards` 表（主键 `id BigInteger`）。
- 复用：既有种子数据（`dance-school` 租户 + 种子 student/teacher/admin，conftest 初始化）。
- 复用：既有 `users` 表（订单 `user_id` FK 指向种子 student）。
- 无新外部依赖；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响；无 Service/Repository 改动。
- 前置 Feature F4.1（提供 `down_revision=f41ab2c3d4e5` 链接点）。

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他模块直接写 `orders.membership_card_id` 绕过 Service | grep `Order(` / `INSERT INTO orders` / `orders.membership_card_id`：仅命中 order/models.py（模型定义）、payment/service.py L61-63（只读日志）、57aeb9dcf020 migration（建列）。无任何业务路径通过 ORM 创建 Order 或裸 SQL 直写该列 → 加 FK 不破坏任何既有写入路径 |
| U2 | 生产灰度时是否有新增孤立数据在 upgrade 瞬间产生 | upgrade 的 UPDATE + ADD CONSTRAINT + CREATE INDEX 在同一事务内（alembic `Will assume transactional DDL`），事务隔离下并发写入非空 card_id 在 ADD CONSTRAINT 阶段会因 FK 校验失败而整体回滚；但 upgrade 前无 FK，并发写入仍可产生新孤立（在 UPDATE 之后 ADD 之前）。生产灰度建议在维护窗口或先停写。dev 库无此问题（orders 0 行） |
| U3 | `ON DELETE SET NULL` 触发时定位引用行开销 | 本 Feature 已加索引 `ix_orders_membership_card_id`，PG 触发器按索引定位引用行；无全表扫描风险。dev 库 orders 0 行，索引收益在生产高量级时体现 |
| U4 | 是否有按卡反查订单的业务场景受益于该索引 | 当前 order 模块仅有 models.py（无 service/router/repository），但未来支付/对账/退卡场景按卡查订单是可预期路径；本 Feature 顺手建索引避免后续单独 migration |
| U5 | downgrade 是否恢复孤立数据 | 不可能：孤立引用指向的卡本不存在，无可恢复信息；downgrade 仅 drop index + drop FK |
