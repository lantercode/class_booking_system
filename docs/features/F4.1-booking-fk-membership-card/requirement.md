# F4.1 — 恢复 bookings.membership_card_id 外键 · 需求文档

> Feature ID：F4.1
> 作者：database-engineer
> 日期：2026-09-29
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（纯数据库结构任务，单领域轨道，不召前端/后端业务层；不动 Service/Repository 逻辑）
> 依赖：无新外部依赖；复用既有 `membership_cards` 表（主键 `id BigInteger`）
> 前置 Feature：无（init_all_tables 原本就有该 FK，后被丢失，本 Feature 恢复）

---

## Goal

预约必须引用存在的会员卡。`bookings.membership_card_id` 当前只是一列 `BigInteger`，没有外键约束，DB 无法阻止插入指向不存在 `membership_cards.id` 的引用——已实测存在 **4 条孤立 booking**（`membership_card_id` 指向不存在的卡）。

修复目标：用一条 Alembic migration 在同一事务内先清理孤立引用（把指向不存在卡的 `membership_card_id` 置 NULL），再重建外键 `fk_bookings_membership_card_id`（`ON DELETE SET NULL`），并在 ORM 模型层补回 `ForeignKey("membership_cards.id", ondelete="SET NULL")` 使模型与 DB 一致。

## User Story

作为系统，
我希望 `bookings.membership_card_id` 在数据库层有外键约束（`ON DELETE SET NULL`），以便：
- DB 直接拒绝插入指向不存在会员卡的预约，不再依赖应用层兜底。
- 会员卡被删除时，关联预约的 `membership_card_id` 自动置 NULL（预约本身保留，业务层在取消/回补课时前会 `if booking.membership_card_id:` 短路，安全）。
- 消除已存在的 4 条孤立引用（它们指向的卡本就不存在，置 NULL 后语义与"无关联卡"一致）。

作为运维，
我希望 migration 有完整 upgrade + downgrade 且 revision 链正确（`down_revision=211f847af16c` 当前唯一 head），以便生产灰度与回滚可审计。

## Background / 现状（已核查的代码与 DB 事实）

| 事实 | 证据 |
|------|------|
| `Booking.membership_card_id` 当前只有 `BigInteger` 无 FK | [models.py:52-56](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L52-56)（修复前）：`membership_card_id: Mapped[int \| None] = mapped_column(BigInteger, nullable=True)` |
| init migration 原本定义了该 FK | [4bd04b738098_init_all_tables.py:486-488](file:///Users/lixiang/Desktop/class_booking_system/apps/api/alembic/versions/4bd04b738098_init_all_tables.py#L486-488)：`sa.ForeignKeyConstraint(["membership_card_id"], ["membership_cards.id"], ondelete="SET NULL")` —— 后随模型简化丢失，DB 中亦不存在 |
| bookings 表当前无该 FK | 实测 `pg_constraint`：仅 `bookings_pkey` / `bookings_public_id_key` / `bookings_schedule_id_fkey`(RESTRICT) / `bookings_student_id_fkey`(RESTRICT) / `bookings_tenant_id_fkey`(CASCADE) |
| 存在 4 条孤立 booking | 实测：`SELECT COUNT(*) FROM bookings b LEFT JOIN membership_cards m ON b.membership_card_id=m.id WHERE b.membership_card_id IS NOT NULL AND m.id IS NULL` → 4（bookings 总 11 / 非空 card_id 10 / membership_cards 17） |
| `MembershipCard.id` 为 `BigInteger` 主键 | [membership/models.py:160](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L160)：`id: Mapped[int] = mapped_column(BigInteger, primary_key=True)` |
| 当前 alembic 唯一 head | `alembic heads` → `211f847af16c (head)`；无其他 migration 以其为 `down_revision` |
| `membership_card_id` 无索引 | 实测 `pg_indexes` for `bookings`：无 `membership_card_id` 相关索引 |
| 业务层已处理 `membership_card_id IS NULL` | [schedule/service.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py) 与 [booking/service.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py)：取消/回补前均 `if booking.membership_card_id:` 短路 → 置 NULL 安全 |
| 同类模式已存在 | [MembershipCardTransaction.booking_id](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L278-283)：`ForeignKey("bookings.id", ondelete="SET NULL")` —— 反向引用 booking，同样 SET NULL |

## Scope（In Scope）

1. 新增 Alembic migration `f41ab2c3d4e5_restore_bookings_membership_card_fk`：
   - `down_revision = "211f847af16c"`（当前唯一 head）。
   - `upgrade`：先 `UPDATE bookings SET membership_card_id = NULL WHERE membership_card_id IS NOT NULL AND membership_card_id NOT IN (SELECT id FROM membership_cards)` 清理孤立；再 `op.create_foreign_key(..., ondelete="SET NULL")` 重建 FK `fk_bookings_membership_card_id`。
   - `downgrade`：`op.drop_constraint("fk_bookings_membership_card_id", "bookings", type_="foreignkey")`；已清理的孤立数据无法恢复（原始指向的卡本就不存在）。
2. `apps/api/src/app/modules/booking/models.py`：`membership_card_id` 列补 `ForeignKey("membership_cards.id", ondelete="SET NULL")`，与 migration 一致。
3. 新增集成测试 `apps/api/tests/integration/test_booking_fk_membership_card.py`：6 用例覆盖 FK 存在性 / 正常引用 / IntegrityError / ON DELETE SET NULL / 孤立计数=0 / migration 清理逻辑本身正确。

## Out of Scope

- 不修改 Service / Repository / Router / schemas（FK 约束在 DB 层；业务层已 `if booking.membership_card_id:` 短路，置 NULL 安全）。
- 不新增 `membership_card_id` 索引（F4.2 范围是 `orders.membership_card_id` 外键+索引；bookings 侧按需另立 Feature 评估，本 Feature 不扩大范围）。
- 不修改 OpenAPI 契约（无端点变化）。
- 不修改前端 4 端 / MCP。
- 不引入新依赖。
- 不处理 `orders.membership_card_id`（F4.2 范围）。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1：FK `fk_bookings_membership_card_id` 存在且 `ON DELETE SET NULL`。
- AC-2：创建 booking 引用存在的卡 → 成功，`membership_card_id` 落库。
- AC-3：创建 booking 引用不存在的 `card_id` → `IntegrityError`（FK 校验生效）。
- AC-4：删除 card → 关联 booking 的 `membership_card_id` 变 NULL（`ON DELETE SET NULL`）。
- AC-5：migration 已清理孤立数据（孤立计数 == 0）。
- AC-6：migration 清理逻辑本身正确（事务内复刻：drop FK → 插孤立 → 清理 UPDATE → `card_id` 变 NULL → re-add FK 成功；整体回滚不污染 dev DB）。

## Dependencies

- 复用：既有 `membership_cards` 表（主键 `id BigInteger`）。
- 复用：既有种子数据（`dance-school` 租户 + 种子 student/teacher/admin，conftest 初始化）。
- 无新外部依赖；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响；无 Service/Repository 改动。

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 4 条孤立 booking 被置 NULL 后，业务层取消这些预约时是否漏回补课时 | 这些 booking 指向的卡本就不存在（无法回补）；业务层 `if booking.membership_card_id:` 短路 → 置 NULL 后语义为"无关联卡"，取消时不触发 restore_credit，与既有"无卡预约"行为一致，安全 |
| U2 | 是否需要给 `membership_card_id` 加索引以加速 SET NULL 时的行定位 | `ON DELETE SET NULL` 时 PG 需定位引用行；当前 bookings 量级小，无索引可接受；按 schedule_id/student_id 已有复合索引（含 tenant）。索引优化属另一 Feature 范围，本 Feature 不扩大 |
| U3 | downgrade 是否恢复孤立数据 | 不可能：孤立引用指向的卡本就不存在，无可恢复信息；downgrade 仅 drop FK |
| U4 | 生产灰度时若有新增孤立数据在 upgrade 瞬间产生 | upgrade 的 UPDATE + ADD CONSTRAINT 在同一事务内（alembic `Will assume transactional DDL`），事务隔离下并发插入非空 card_id 必须通过既有 FK 校验... 实际上 upgrade 前无 FK，并发写入仍可能产生新孤立；生产灰度建议在维护窗口或先停写。dev 库无此问题 |
