# F4.1 — 恢复 bookings.membership_card_id 外键 · 实施方案

> Feature ID：F4.1
> 作者：database-engineer
> 日期：2026-09-29
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

`bookings.membership_card_id` 在 init migration（`4bd04b738098`）原本有 `ForeignKeyConstraint(["membership_card_id"], ["membership_cards.id"], ondelete="SET NULL")`，后随 ORM 模型简化（`Booking` 模型该列改为纯 `BigInteger`），DB 中该约束亦丢失。当前：

1. **DB 无 FK**：实测 `pg_constraint` for `bookings` 仅有 `bookings_pkey` / `bookings_public_id_key` / `bookings_schedule_id_fkey` / `bookings_student_id_fkey` / `bookings_tenant_id_fkey`，无 `membership_card_id` 外键。
2. **存在 4 条孤立**：`SELECT COUNT(*) ... WHERE membership_card_id IS NOT NULL AND m.id IS NULL` → 4（指向不存在的卡）。
3. **模型无 FK**：`Booking.membership_card_id` 仅 `BigInteger`。

直接 `ADD CONSTRAINT` 会因 4 条孤立失败，故必须先清理再建约束。

## 已核查的代码与 DB 事实（Evidence）

| 事实 | 证据 |
|------|------|
| 模型当前无 FK | [models.py:52-56](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L52-56)（修复前）：`mapped_column(BigInteger, nullable=True)` |
| init migration 原有 FK | [4bd04b738098:486-488](file:///Users/lixiang/Desktop/class_booking_system/apps/api/alembic/versions/4bd04b738098_init_all_tables.py#L486-488) |
| 当前 alembic head | `alembic heads` → `211f847af16c`（唯一，无其他 migration 以其为 down_revision） |
| DB 有 4 条孤立 | 实测 `SELECT COUNT(*) ...` → 4 |
| `MembershipCard.id` BigInteger 主键 | [membership/models.py:160](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L160) |
| 业务层处理 NULL card_id | schedule/booking Service 均有 `if booking.membership_card_id:` 短路（见 F2.4 验证） |
| env.py 用 async + target_metadata=Base.metadata | [env.py:34](file:///Users/lixiang/Desktop/class_booking_system/apps/api/alembic/env.py#L34) |
| alembic 事务化 DDL | upgrade 输出 `Will assume transactional DDL` → UPDATE + ALTER 同一事务 |

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/alembic/versions/f41ab2c3d4e5_restore_bookings_membership_card_fk.py` | 新建 migration：`revision=f41ab2c3d4e5` / `down_revision=211f847af16c`；upgrade=清理 UPDATE + create_foreign_key(SET NULL)；downgrade=drop_constraint |
| 2 | `apps/api/src/app/modules/booking/models.py` | `membership_card_id` 列补 `ForeignKey("membership_cards.id", ondelete="SET NULL")`（与 migration 一致） |
| 3 | `apps/api/tests/integration/test_booking_fk_membership_card.py` | 新建，6 用例覆盖 AC-1~AC-6 |

**不在改动范围**：Service / Repository / Router / schemas / OpenAPI / 前端 / MCP / Redis。

## Exact Fix

### migration（`f41ab2c3d4e5_restore_bookings_membership_card_fk.py`）

```python
FK_NAME = "fk_bookings_membership_card_id"

def upgrade() -> None:
    # 1. 清理孤立（T4.1.1）
    op.execute(sa.text("""
        UPDATE bookings
           SET membership_card_id = NULL
         WHERE membership_card_id IS NOT NULL
           AND membership_card_id NOT IN (SELECT id FROM membership_cards)
    """))
    # 2. 加 FK（T4.1.2）
    op.create_foreign_key(
        constraint_name=FK_NAME,
        source_table="bookings",
        referent_table="membership_cards",
        local_cols=["membership_card_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )

def downgrade() -> None:
    op.drop_constraint(FK_NAME, "bookings", type_="foreignkey")
```

### 模型对齐（`booking/models.py` L52-56）

```python
membership_card_id: Mapped[int | None] = mapped_column(
    BigInteger,
    ForeignKey("membership_cards.id", ondelete="SET NULL"),
    nullable=True,
)
```

## 关键决策记录（Decision）

| # | 决策 | 理由 |
|---|------|------|
| D1 | 清理 + 建 FK 在同一 migration、同一事务 | alembic `Will assume transactional DDL` → UPDATE + ALTER 在一个事务内原子完成；若 UPDATE 失败则 FK 不加，DB 维持原状，不会出现"清理了但没加约束"的中间态 |
| D2 | 清理用 `UPDATE ... SET NULL WHERE ... NOT IN (SELECT id FROM membership_cards)` | 标准反连接清理语义；`WHERE membership_card_id IS NOT NULL` 跳过已 NULL 行；NULL 值在 `NOT IN` 下不匹配（已被 IS NOT NULL 过滤） |
| D3 | `ON DELETE SET NULL` 而非 `RESTRICT` | 与 init migration 原设计一致；业务层取消 booking 前已 `if booking.membership_card_id:` 短路，删卡时把引用置 NULL 安全（预约本身保留）；`RESTRICT` 会让删卡失败，破坏既有会员卡删除流程 |
| D4 | 模型补 `ForeignKey` | 模型与 DB 一致；避免 `alembic autogenerate` 误报 diff；ORM 在 `INSERT` 时也能反映 FK 语义 |
| D5 | 约束名显式 `fk_bookings_membership_card_id` | 便于 downgrade 精确 drop；避免 PG 自动命名（`bookings_membership_card_id_fkey`）在不同环境不一致 |
| D6 | downgrade 不恢复孤立数据 | 不可能：孤立指向的卡本就不存在，无可恢复信息；downgrade 仅 drop FK |
| D7 | 不新增 `membership_card_id` 索引 | bookings 量级小；`ON DELETE SET NULL` 行定位开销可接受；索引优化属另一 Feature 范围，不扩大本 Feature scope |
| D8 | 不改 Service/Repository | FK 在 DB 层；业务层已处理 NULL card_id；Service 零改动降低回归面 |

## Dependency Analysis

- 复用：既有 `membership_cards` 表（主键 `id BigInteger`）。
- 复用：既有种子数据（conftest 初始化 `dance-school` 租户 + 种子用户）。
- 无新外部依赖；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响。
- 契约：无端点变化 → 无需 `pnpm gen:types`，前端 4 端无影响。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 置 NULL 4 条孤立后业务层漏回补 | 低 | 这些 booking 指向的卡本不存在（无法回补）；业务层 `if booking.membership_card_id:` 短路 → 与"无卡预约"行为一致 |
| `ON DELETE SET NULL` 触发时定位引用行开销 | 低 | bookings 量级小（11 行）；无索引也足够；高量级时另加索引（F4.x） |
| 生产灰度时并发写入产生新孤立 | 中 | upgrade 前 DB 无 FK，并发写入仍可产生孤立；建议生产在维护窗口或先停写再 upgrade。dev 库无此问题（已验证） |
| migration revision 链断裂 | 低 | `down_revision=211f847af16c`（实测唯一 head）；`alembic heads` 验证单 head |
| AC-6 测试中 drop/re-add FK 影响 dev DB | 低 | PostgreSQL DDL 事务化；测试在显式事务内执行，最终 `trans.rollback()` 还原；并发连接在事务期间看到旧状态（约束存在） |
| 业务层 Service 创建 booking 时传入无效 card_id 抛 IntegrityError 未被捕获 | 低 | 既有 Service 在创建 booking 前已校验 card 有效性；DB FK 为最后兜底；即便触发，经全局异常处理器返回统一信封 |

## Implementation Steps

1. 写 migration `f41ab2c3d4e5_*.py` → py_compile。
2. `alembic upgrade head` 应用 → 验证孤立=0 + FK 存在。
3. `alembic downgrade -1` + `alembic upgrade head` 验证可逆。
4. 改 `booking/models.py` 补 ForeignKey → py_compile。
5. 写 `test_booking_fk_membership_card.py`（6 用例）→ 迭代至全绿。
6. 静态审查 diff（仅 migration + model + 新测试）。
7. 回归 `test_cancel_schedule_rollback.py` + `test_booking_ownership.py` + `test_checkin_complete_lock.py`。

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1 | `test_fk_constraint_exists_with_on_delete_set_null` |
| AC-2 | `test_booking_with_valid_membership_card_succeeds` |
| AC-3 | `test_booking_with_nonexistent_card_raises_integrity_error` |
| AC-4 | `test_delete_card_sets_booking_card_id_null` |
| AC-5 | `test_no_orphan_bookings_after_migration` |
| AC-6 | `test_migration_cleanup_clears_orphan_and_readds_fk` |
| AC-7 | 回归 `test_cancel_schedule_rollback.py` + `test_booking_ownership.py` + `test_checkin_complete_lock.py` |
| AC-8 | 静态 grep：Service/Repository 零改动；模型与 migration FK 一致 |
| AC-9 | `alembic downgrade -1` + `alembic upgrade head` 往返 |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他模块直接写 `bookings.membership_card_id` 绕过 Service | grep `membership_card_id` 仅命中 booking/schedule/payment Service + order/booking models + migration + 既有测试，均在 Service/Repository 层；无裸 SQL 直写 bookings |
| U2 | AC-6 测试 drop FK 期间并发连接是否受影响 | PostgreSQL DDL 事务化，ALTER TABLE 在事务内未 commit 前，并发连接看到旧状态（FK 仍在），仅本事务内可见 drop；rollback 还原，无影响 |
| U3 | `MembershipCardTransaction.booking_id` 已有 FK 指向 bookings（SET NULL），删 booking 时 txn 的 booking_id 置 NULL；本 Feature 是否影响 | 不影响：本 Feature 加的是 bookings→membership_cards 的 FK（反向），与 txn→bookings 的 FK 独立 |
