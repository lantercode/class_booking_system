# F4.4 — 核心表 status 字段 Check 约束 · 需求文档

> Feature ID：F4.4
> 作者：database-engineer
> 日期：2026-10-02
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（纯数据库结构任务，单领域轨道，不召前端/后端业务层；不动 Service/Repository 逻辑）
> 依赖：无新外部依赖；复用既有 `bookings` / `course_schedules` / `membership_cards` 三表
> 前置 Feature：F4.2（orders FK + 索引，已完成；当前 alembic head = `f42cd3e4f5a6`）

---

## Goal

数据库层防止非法状态值写入核心三表。`bookings.status` / `course_schedules.status` / `membership_cards.status` 当前仅有应用层（Service / Pydantic）校验，DB 层无任何 status 取值约束——任何绕过 Service 的写入路径（手写 SQL、数据修复脚本、未来新代码缺陷）都可能把状态字段写成枚举外的非法值，且一旦写入难以发现。

修复目标：用一条 Alembic migration 在同一事务内先做越界防御性校验（fail-fast），再为三表分别 `ADD CONSTRAINT ... CHECK (status IN (...))`；并在三张 ORM 模型的 `__table_args__` 中补同名 `CheckConstraint`，使模型与 DB 一致。

## User Story

作为系统，
我希望三张核心表的 `status` 在数据库层有 Check 约束，以便：
- DB 直接拒绝枚举外的非法状态值（`IntegrityError`），不再依赖应用层兜底；
- 状态机取值集合在 DB 层成为可审计的事实源（与 ORM 枚举一一对应）。

作为运维，
我希望 migration 在发现存量越界数据时 fail-fast 并打印明细（表 / status 值 / 行数），而不是静默篡改业务状态，以便人工核查后重跑。

作为运维，
我希望 migration 有完整 upgrade + downgrade 且 revision 链正确（`down_revision=f42cd3e4f5a6` F4.2 后唯一 head），以便生产灰度与回滚可审计。

## Background / 现状（已核查的代码与 DB 事实）

| 事实 | 证据 |
|------|------|
| `Booking.status` 为 `SmallInteger` 无 Check 约束，枚举 `BookingStatus = {1,2,3,4,5}` | [booking/models.py:12-17](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L12-L17)（枚举）与 [booking/models.py:46](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L46)（列定义）；`__table_args__` 仅 3 个 Index，无 CheckConstraint |
| `CourseSchedule.status` 为 `SmallInteger`（default=1），枚举 `ScheduleStatus = {1,2,3}` | [schedule/models.py:12-15](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/models.py#L12-L15) 与 [schedule/models.py:49-53](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/models.py#L49-L53)；既有 Check 仅 `chk_schedule_time` / `chk_schedule_capacity`，无 status |
| `MembershipCard.status` 为 `SmallInteger`（default=0），枚举 `CardStatus = {0,1,2,3,6}` | [membership/models.py:49-56](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L49-L56) 与 [membership/models.py:207-212](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L207-L212)；既有 Check 仅 `chk_credits_range`，无 status |
| DB 三表均无 status Check 约束 | 实测 `pg_constraint contype='c'`：bookings 0 个；course_schedules 仅 `chk_schedule_capacity` / `chk_schedule_time`；membership_cards 仅 `chk_used_credits_valid` / `chk_total_credits_positive` |
| DB 三表均无越界 status | 实测 `GROUP BY status`：bookings `{2:3, 5:8}`（共 11 行）；course_schedules `{2:2, 3:31}`（共 33 行）；membership_cards `{0:2, 1:6, 2:4, 3:1, 6:4}`（共 17 行）；全部落在合法集合内 |
| 当前 alembic 唯一 head | 实测 `alembic_version = f42cd3e4f5a6`（F4.2）；无其他 migration 以其为 `down_revision` |
| 枚举值与 backlog 定义一致 | backlog T4.4.1/4.4.2/4.4.3 合法集合 = ORM 枚举集合，逐一比对无差异 |
| 同类模式已存在 | F4.1 [f41ab2c3d4e5](file:///Users/lixiang/Desktop/class_booking_system/apps/api/alembic/versions/f41ab2c3d4e5_restore_bookings_membership_card_fk.py) / F4.2 [f42cd3e4f5a6](file:///Users/lixiang/Desktop/class_booking_system/apps/api/alembic/versions/f42cd3e4f5a6_restore_orders_membership_card_fk_and_index.py)：同一事务内先处理存量再建约束 |

## Scope（In Scope）

1. 新增 Alembic migration `f44ab1c2d3e4_add_status_check_constraints`：
   - `down_revision = "f42cd3e4f5a6"`（F4.2 后唯一 head）。
   - `upgrade`（同一事务，原子完成）：
     1. 越界防御性校验：逐表 `SELECT status, COUNT(*) ... WHERE status NOT IN (...)`，任一表存在越界行即 `raise RuntimeError`（打印表/值/行数明细），整批回滚；
     2. `op.create_check_constraint("ck_bookings_status", "bookings", "status IN (1, 2, 3, 4, 5)")`；
     3. `op.create_check_constraint("ck_course_schedules_status", "course_schedules", "status IN (1, 2, 3)")`；
     4. `op.create_check_constraint("ck_membership_cards_status", "membership_cards", "status IN (0, 1, 2, 3, 6)")`。
   - `downgrade`：按反序 `op.drop_constraint(..., type_="check")` 三个约束（不动数据）。
2. 模型对齐（`__table_args__` 补同名 `CheckConstraint`）：
   - `apps/api/src/app/modules/booking/models.py`（补 `CheckConstraint` import + `ck_bookings_status`）；
   - `apps/api/src/app/modules/schedule/models.py`（补 `ck_course_schedules_status`）；
   - `apps/api/src/app/modules/membership/models.py`（补 `ck_membership_cards_status`）。
3. 新增集成测试 `apps/api/tests/integration/test_status_check_constraints.py`：18 用例覆盖约束存在性 / 非法值 IntegrityError / 合法边界与中间值放行 / 存量数据未破坏。

## Out of Scope

- 不修改 Service / Repository / Router / schemas（Check 约束在 DB 层，对业务层透明）。
- 不修改 OpenAPI 契约（无端点变更）。
- 不修改前端 4 端 / MCP。
- 不引入新依赖。
- 不给其他带 status 的表（users / courses / classrooms / orders 等）加约束（backlog 未要求，遵循"不为不存在的需求增加数据库结构"）。
- 不处理既有模型/DB 约束命名漂移（membership_cards 模型 `chk_credits_range` vs DB `chk_used_credits_valid`+`chk_total_credits_positive`：存量差异，与本 Feature 无关，记入 UNKNOWN）。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1/2/3：三个 Check 约束存在且定义正确。
- AC-4/5/6：三表插入非法 status → `IntegrityError`。
- AC-7/8/9：三表插入合法边界值与中间值 → 成功。
- AC-10：migration 未破坏存量数据（越界计数 == 0 且存量行数不变）。
- AC-11：回归不破现有行为（F4.1 6/6 + F4.2 7/7）。
- AC-12：分层合规（Service/Repository/Router/schemas 零改动）。
- AC-13：migration 可逆（downgrade→upgrade 往返成功）。

## Dependencies

- 复用：既有三表及其 `status SmallInteger NOT NULL` 列。
- 复用：既有种子数据（`dance-school` 租户 + 种子 student/teacher，conftest 初始化）与既有 courses 行（排期 FK 需要）。
- 前置 Feature F4.2（提供 `down_revision=f42cd3e4f5a6` 链接点）。
- 无新外部依赖；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响；无 Service/Repository 改动。

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 生产库是否存在越界 status 行 | dev 库实测 0 越界；生产不可知 → upgrade 采用 fail-fast 校验：发现越界即抛错回滚并打印明细，人工修正后重跑；绝不静默 UPDATE 业务状态 |
| U2 | 业务层是否依赖"写非法 status 不报错"的行为 | grep Service 层状态机：所有 status 赋值均来自对应枚举（`BookingStatus` / `ScheduleStatus` / `CardStatus`）的 `.value`，合法集合 = 枚举集合 → 加约束不破坏任何既有写入路径 |
| U3 | membership_cards 模型 `chk_credits_range` 与 DB `chk_used_credits_valid`/`chk_total_credits_positive` 命名漂移 | 存量历史差异（本 Feature 前已存在）；不影响本 Feature（新约束名 `ck_membership_cards_status` 模型与 DB 一致）；如未来做 autogenerate 需另行对齐，另立 Feature |
| U4 | downgrade 是否需要恢复数据 | 不需要：Check 约束不修改存量数据，downgrade 仅 drop 约束 |
