# F4.2 — 恢复 orders.membership_card_id 外键 + 索引 · 实施方案

> Feature ID：F4.2
> 作者：database-engineer
> 日期：2026-09-29
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

`orders.membership_card_id` 在 `57aeb9dcf020` migration 新增列时仅落库 `BigInteger`，未带外键；`Order` ORM 模型亦无 `ForeignKey`，`__table_args__` 亦无该列索引。当前：

1. **DB 无 FK**：实测 `pg_constraint` for `orders` 仅有 `orders_tenant_id_fkey`(CASCADE) / `orders_user_id_fkey`(RESTRICT)，无 `membership_card_id` 外键。
2. **DB 无索引**：实测 `pg_indexes` for `orders`：`orders_pkey` / `orders_order_no_key` / `orders_public_id_key` / `idx_orders_status_created` / `idx_orders_user` / `ix_orders_tenant_id`，无 `membership_card_id` 索引。
3. **孤立 = 0**：dev 库 orders 0 行，孤立 0（生产可能非 0，需防御性清理）。
4. **模型无 FK 无 Index**：`Order.membership_card_id` 仅 `BigInteger`；`__table_args__` 仅含 `idx_orders_user` + `idx_orders_status_created`。

直接 `ADD CONSTRAINT` 在 dev 库当前可成功（无孤立），但生产可能有孤立 → migration 必须先清理再建约束（与 F4.1 同范式）。

## 已核查的代码与 DB 事实（Evidence）

| 事实 | 证据 |
|------|------|
| 模型当前无 FK 无 Index | [models.py:58-69](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/order/models.py#L58-69)（修复前）：`membership_card_id` 仅 BigInteger；`__table_args__` 无 `ix_orders_membership_card_id` |
| 建列 migration 无 FK | [57aeb9dcf020:22-34](file:///Users/lixiang/Desktop/class_booking_system/apps/api/alembic/versions/57aeb9dcf020_add_membership_card_id_to_orders_table.py#L22-34)：仅 `op.add_column` |
| 当前 alembic head | `alembic heads` → `f41ab2c3d4e5`（F4.1，唯一 head） |
| DB 无孤立 | 实测 `SELECT COUNT(*) ...` → 0（orders 0 行） |
| DB 无 FK | 实测 `pg_constraint` for `orders`：仅 `orders_tenant_id_fkey` / `orders_user_id_fkey` |
| DB 无索引 | 实测 `pg_indexes` for `orders`：6 个索引，无 `membership_card_id` 相关 |
| `MembershipCard.id` BigInteger 主键 | [membership/models.py:160](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L160) |
| 业务层仅读不写 | grep `Order(` 仅命中模型定义；grep `orders.membership_card_id` 仅命中 payment/service.py L61-63（只读日志）；无裸 `INSERT INTO orders` SQL |
| env.py 用 async + target_metadata=Base.metadata | [env.py:34](file:///Users/lixiang/Desktop/class_booking_system/apps/api/alembic/env.py#L34) |
| alembic 事务化 DDL | upgrade 输出 `Will assume transactional DDL` → UPDATE + ALTER + CREATE INDEX 同一事务 |
| 同类模式已存在（F4.1） | [f41ab2c3d4e5](file:///Users/lixiang/Desktop/class_booking_system/apps/api/alembic/versions/f41ab2c3d4e5_restore_bookings_membership_card_fk.py)：bookings 同范式（清理 UPDATE + create_foreign_key SET NULL）—— 本 Feature 复用并扩展加索引 |

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/alembic/versions/f42cd3e4f5a6_restore_orders_membership_card_fk_and_index.py` | 新建 migration：`revision=f42cd3e4f5a6` / `down_revision=f41ab2c3d4e5`；upgrade=清理 UPDATE + create_foreign_key(SET NULL) + create_index；downgrade=drop_index + drop_constraint |
| 2 | `apps/api/src/app/modules/order/models.py` | `membership_card_id` 列补 `ForeignKey("membership_cards.id", ondelete="SET NULL")`；`__table_args__` 补 `Index("ix_orders_membership_card_id", "membership_card_id")` |
| 3 | `apps/api/tests/integration/test_order_fk_membership_card.py` | 新建，7 用例覆盖 AC-1~AC-7 |

**不在改动范围**：Service / Repository / Router / schemas / OpenAPI / 前端 / MCP / Redis / payment service。

## Exact Fix

### migration（`f42cd3e4f5a6_restore_orders_membership_card_fk_and_index.py`）

```python
FK_NAME = "fk_orders_membership_card_id"
INDEX_NAME = "ix_orders_membership_card_id"

def upgrade() -> None:
    # 1. 清理孤立（T4.2.1 前置）
    op.execute(sa.text("""
        UPDATE orders
           SET membership_card_id = NULL
         WHERE membership_card_id IS NOT NULL
           AND membership_card_id NOT IN (SELECT id FROM membership_cards)
    """))
    # 2. 加 FK（T4.2.1）
    op.create_foreign_key(
        constraint_name=FK_NAME,
        source_table="orders",
        referent_table="membership_cards",
        local_cols=["membership_card_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
    # 3. 加索引（T4.2.2）
    op.create_index(
        index_name=INDEX_NAME,
        table_name="orders",
        columns=["membership_card_id"],
    )

def downgrade() -> None:
    # 先 drop index 再 drop FK（与 upgrade 反序）
    op.drop_index(index_name=INDEX_NAME, table_name="orders")
    op.drop_constraint(constraint_name=FK_NAME, table_name="orders", type_="foreignkey")
```

### 模型对齐（`order/models.py` L58-69）

```python
membership_card_id: Mapped[int | None] = mapped_column(
    BigInteger,
    ForeignKey("membership_cards.id", ondelete="SET NULL"),
    nullable=True,
    comment="关联会员卡ID（购买次卡时生成）",
)

__table_args__ = (
    Index("idx_orders_user", "tenant_id", "user_id", "status"),
    Index("idx_orders_status_created", "tenant_id", "status", text("created_at DESC")),
    Index("ix_orders_membership_card_id", "membership_card_id"),
)
```

## 关键决策记录（Decision）

| # | 决策 | 理由 |
|---|------|------|
| D1 | 清理 + 建 FK + 建索引在同一 migration、同一事务 | alembic `Will assume transactional DDL` → UPDATE + ALTER + CREATE INDEX 在一个事务内原子完成；若 UPDATE 失败则 FK 与索引不加，DB 维持原状，不会出现"清理了但没加约束/索引"的中间态 |
| D2 | 清理用 `UPDATE ... SET NULL WHERE ... NOT IN (SELECT id FROM membership_cards)` | 标准反连接清理语义；`WHERE membership_card_id IS NOT NULL` 跳过已 NULL 行；NULL 值在 `NOT IN` 下不匹配（已被 IS NOT NULL 过滤）；与 F4.1 同范式 |
| D3 | `ON DELETE SET NULL` 而非 `RESTRICT` | 与 F4.1 bookings 同范式（`membership_cards.id` 全局主键被多表引用，RESTRICT 会让删卡失败破坏既有流程）；业务层 `payment/service.py` L61 已 `if order.membership_card_id:` 短路 → 删卡时置 NULL 安全（订单本身保留） |
| D4 | 模型补 `ForeignKey` + `Index` | 模型与 DB 一致；避免 `alembic autogenerate` 误报 diff；ORM 在 `INSERT` 时也能反映 FK 语义；索引元数据在模型层声明便于未来 autogenerate 一致性 |
| D5 | 约束名显式 `fk_orders_membership_card_id`、索引名显式 `ix_orders_membership_card_id` | 便于 downgrade 精确 drop；避免 PG 自动命名（`orders_membership_card_id_fkey`）在不同环境不一致；命名与 F4.1 `fk_bookings_membership_card_id` 同构 |
| D6 | downgrade 顺序：先 drop index 再 drop FK | 与 upgrade 反序；避免 drop FK 时触发依赖索引的副作用（虽然 PG drop FK 不强制 drop 关联索引，但反序更安全可审计） |
| D7 | downgrade 不恢复孤立数据 | 不可能：孤立指向的卡本不存在，无可恢复信息；downgrade 仅 drop index + drop FK |
| D8 | 索引不含 `tenant_id` 前缀 | 该索引用于 FK 触发的 `UPDATE orders SET membership_card_id=NULL WHERE membership_card_id=<x>` 行定位（PG 触发器不经过租户过滤），以及未来按卡反查订单（按 card_id 全局唯一）；按租户列表查询走既有 `idx_orders_user` / `idx_orders_status_created` 复合索引 |
| D9 | 不改 Service/Repository | FK + 索引在 DB 层；业务层已处理 NULL card_id；order 模块当前仅有 models.py（无 service/router/repository）；Service/Repository 零改动降低回归面 |
| D10 | 顺手建索引（F4.1 评估时 bookings 未建索引） | F4.1 D7 评估 bookings 量级小未建索引；本 Feature 范围明确要求"外键 + 索引"，orders 同样量级小但 Task 定义要求建索引 → 严格按 Task T4.2.2 执行 |

## Dependency Analysis

- 复用：既有 `membership_cards` 表（主键 `id BigInteger`）。
- 复用：既有种子数据（conftest 初始化 `dance-school` 租户 + 种子用户）。
- 复用：既有 `users` 表（订单 `user_id` FK 指向种子 student）。
- 前置 Feature：F4.1 提供 `down_revision=f41ab2c3d4e5` 链接点。
- 无新外部依赖；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响。
- 契约：无端点变化 → 无需 `pnpm gen:types`，前端 4 端无影响。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 置 NULL 孤立后业务层漏回补 | 低 | order 模块当前无 Service；payment/service.py L61 仅读不写；置 NULL 后日志分支跳过，与"无关联卡"行为一致 |
| `ON DELETE SET NULL` 触发时定位引用行开销 | 低 | 本 Feature 已加索引 `ix_orders_membership_card_id`，PG 触发器按索引定位；无全表扫描风险 |
| 生产灰度时并发写入产生新孤立 | 中 | upgrade 前 DB 无 FK，并发写入仍可能产生孤立；建议生产在维护窗口或先停写再 upgrade。dev 库无此问题（已验证） |
| migration revision 链断裂 | 低 | `down_revision=f41ab2c3d4e5`（实测唯一 head）；`alembic heads` 验证单 head |
| AC-7 测试中 drop/re-add FK 影响 dev DB | 低 | PostgreSQL DDL 事务化；测试在显式事务内执行，最终 `trans.rollback()` 还原；并发连接在事务期间看到旧状态（约束存在） |
| 业务层创建 order 时传入无效 card_id 抛 IntegrityError 未被捕获 | 低 | order 模块当前无 Service（无 ORM 创建 Order 路径）；即便未来支付流程触发，经全局异常处理器返回统一信封 |
| F4.1 bookings 回归 | 低 | 本 Feature 不动 bookings 表；F4.1 FK 与本 Feature FK 相互独立 |

## Implementation Steps

1. 写 migration `f42cd3e4f5a6_*.py` → py_compile。
2. `alembic upgrade head` 应用 → 验证孤立=0 + FK 存在 + 索引存在。
3. `alembic downgrade -1` + `alembic upgrade head` 验证可逆。
4. 改 `order/models.py` 补 ForeignKey + Index → py_compile。
5. 写 `test_order_fk_membership_card.py`（7 用例）→ 迭代至全绿。
6. 静态审查 diff（仅 migration + model + 新测试）。
7. 回归 `test_booking_fk_membership_card.py`（F4.1）。

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1 | `test_fk_constraint_exists_with_on_delete_set_null` |
| AC-2 | `test_index_on_membership_card_id_exists` |
| AC-3 | `test_order_with_valid_membership_card_succeeds` |
| AC-4 | `test_order_with_nonexistent_card_raises_integrity_error` |
| AC-5 | `test_delete_card_sets_order_card_id_null` |
| AC-6 | `test_no_orphan_orders_after_migration` |
| AC-7 | `test_migration_cleanup_clears_orphan_and_readds_fk` |
| AC-8 | 回归 `test_booking_fk_membership_card.py` |
| AC-9 | 静态 grep：Service/Repository 零改动；模型与 migration FK + Index 一致 |
| AC-10 | `alembic downgrade -1` + `alembic upgrade head` 往返 |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他模块直接写 `orders.membership_card_id` 绕过 Service | grep `Order(` 仅命中模型定义；grep `orders.membership_card_id` 仅命中 payment/service.py L61-63（只读日志）；无裸 `INSERT INTO orders` SQL；无任何业务路径通过 ORM 创建 Order → 加 FK + 索引不破坏既有写入路径 |
| U2 | AC-7 测试 drop FK 期间并发连接是否受影响 | PostgreSQL DDL 事务化，ALTER TABLE 在事务内未 commit 前，并发连接看到旧状态（FK 仍在），仅本事务内可见 drop；rollback 还原，无影响 |
| U3 | F4.1 bookings FK 是否受本 Feature 影响 | 不影响：本 Feature 加的是 orders→membership_cards 的 FK，与 bookings→membership_cards 的 FK 独立；orders 与 bookings 表相互独立 |
| U4 | 索引是否会被 autogenerate 误判为多余 | 不会：模型 `__table_args__` 同步声明 `Index("ix_orders_membership_card_id", "membership_card_id")`，与 migration `create_index` 一致；autogenerate diff 为空 |
