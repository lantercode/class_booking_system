# F6.3 — 会员卡扣次与期卡激活状态机：Implementation Plan

- 状态：DESIGN
- 分组：基线组（按现状完整流程执行，不启用任何效率优化）
- 行号基于 2026-10-22 当前工作区；实施前必须重新对账。
- 本文不包含已执行的代码修改或测试结果。所有测试均为计划，未运行。

## 1. 设计原则

1. 业务规则只在 Service 层实现；Router 只做参数/依赖/响应，Scheduler 只做租户遍历与任务编排（`.trae/rules/architecture/layering.md`）。
2. 跨模块只调用对方 Service；不新增对 `membership/*/repository.py`、`course/*/repository.py`、`schedule/*/repository.py` 的直接调用（`layering.md` 的禁止路径）。
3. 同一业务流程共享一个 `AsyncSession`，最后统一 `commit()`；下游写失败必须抛出以触发回滚，禁止吞异常后继续提交（`.trae/rules/database/transaction.md:8-13`）。
4. 行锁顺序：`booking → schedule → membership card`；卡多行锁按 `id ASC`（`transaction.md:22-25`）。
5. 基线实现：逐租户、逐排期、逐 booking、逐卡循环；不引入批量 upsert、缓存、并行协程、批量锁优化。
6. 所有租户数据访问使用 `TenantAwareRepository` 或显式 `tenant_id`；Scheduler 逐租户 `set_tenant_id`。
7. 不新增公开端点、不改既有 DTO 字段；`validity_days` 仅作为内部持久化字段。

## 2. 目标调用链

```text
HTTP /bookings
  → BookingService.create_booking
      → ScheduleService / ScheduleRepository（现有容量递增）
      → BookingRepository.create(auto_commit=False)
      → MembershipCardService.validate_card_for_booking / validate_period_card_booking
      → MembershipCardService.deduct_credit（仅 count）
      → commit

HTTP /bookings/{id}/complete
  → BookingService.complete_booking
      → BookingRepository.get_by_id_for_update
      → ScheduleService.get_schedule_by_id（读取排期日）
      → MembershipCardService.activate_period_card_on_completion（仅 period）
      → commit

Scheduler auto_finish_expired_schedules
  → BookingService.finalize_schedule_bookings（每个排期）
      → BookingRepository.list_ids_by_schedule
      → BookingRepository.get_by_ids_for_update
      → ScheduleService.lock_schedule_for_update
      → Booking 状态终态
      → MembershipCardService.activate_period_card_on_completion
      → commit

HTTP /membership/cards
  → MembershipCardService.issue_card（period 分支）
  → commit（Router）

Scheduler auto_expire / pending_cancel
  → MembershipCardService.expire_card / cancel_pending_card（逐卡）
  → commit（逐租户）
```

## 3. 任务分解（T6.3.1–T6.3.7）

### T6.3.1 期卡发卡：PENDING + 有效期留空

**改动文件**

- `apps/api/src/app/modules/membership/service.py`
- `apps/api/src/app/modules/membership/models.py`
- `apps/api/alembic/versions/<new_revision>_add_membership_card_validity_days.py`
- （不修改）`apps/api/src/app/modules/membership/schemas.py`、`router.py`

**步骤**

1. `MembershipCard` 新增可空列：
   ```python
   validity_days: Mapped[int | None] = mapped_column(
       SmallInteger, nullable=True, comment="发卡时确定的有效天数快照（期卡激活用）"
   )
   ```
   位置：`membership/models.py:190-191` 的 `valid_from/expire_at` 之后。
2. `issue_card` 在 `validity_days = data.validity_days or product.validity_days`（`membership/service.py:258`）之后分支：
   - `card_type == "period"`：
     - 跳过 `new_card_course_type` 发卡期冲突块（`membership/service.py:265-353`）；
     - 跳过 `allow_duplicate` 续卡最早生效计算（`:355-383`）；
     - `valid_from = None`、`expire_at = None`、`status = CardStatus.PENDING.value`；
     - `validity_days` 写入卡片快照；
     - ISSUE 流水 `change_amount=0`、`balance_after=0`（现有 `:456-468` 已按 `total_credits or 0` 计算，期卡为 0）。
   - 非 period：保持现有 `:397-429` 逻辑不变（`valid_from` 为空/过去 → ACTIVE；未来 → PENDING；`expire_at = _calc_expire_at`）。
3. 期卡仍执行 `:385-391` 的“必须有有效天数”校验；缺 `validity_days` → 400，不落卡。
4. 不修改 `MembershipCardResponse`（`schemas.py:160-214`），避免前端类型再生成；`validity_days` 仅供内部使用。
5. 迁移：
   - `upgrade()`：`op.add_column("membership_cards", sa.Column("validity_days", sa.SmallInteger(), nullable=True, comment="发卡时确定的有效天数快照（期卡激活用）"))`。
   - 回填（见第 7 节）。
   - `downgrade()`：`op.drop_column("membership_cards", "validity_days")`。

**验收映射**：B-1、B-2、B-3、A-7、A-8、A-9。

### T6.3.2 期卡预约校验与预期有效期冲突预校验

**改动文件**

- `apps/api/src/app/modules/membership/service.py`
- `apps/api/src/app/modules/membership/repository.py`
- `apps/api/src/app/modules/booking/service.py`
- `apps/api/src/app/modules/course/service.py`（仅在缺少轻量读取方法时新增）

**新增 Service 方法（MembershipCardService）**

```python
async def validate_card_for_booking(
    self,
    db: AsyncSession,
    *,
    card_id: int,
    tenant_id: int,
    student_id: int,
    schedule_id: int,
    schedule_start_at: datetime,
    course_id: int,
    course_type_code: str | None,
) -> dict:
    """返回 {"card_type": str, "deduct": bool, "validity_days": int | None}"""
```

实现要求：

1. 读取卡（无锁快路径）→ 校验存在、`tenant_id`、`student_id`、`card_type`、状态、排期日有效期、课程适用性。
2. 状态判定：
   - count / unlimited：必须 ACTIVE。
   - period：ACTIVE 或 `PENDING AND valid_from IS NULL`；其余拒绝。
3. 排期日有效期：
   - `schedule_date = schedule_start_at.date()`；
   - `valid_from.date() <= schedule_date <= expire_at.date()`（有值时）；
   - 不得使用 `datetime.now(UTC)` 判断（修复 `membership/service.py:1352-1363`）。
4. 课程适用性：
   - `applicable_course_type_code` 非空且不等于 `course_type_code` → 400 “该会员卡不适用于此课程类型”；
   - `applicable_course_ids` 非空且 `course_id not in` → 400 “该会员卡不适用于此课程”。
5. 返回 `deduct=True` 仅当 `card_type == "count"`；period/unlimited 返回 `deduct=False`。

**新增期卡预校验方法**

```python
async def validate_period_card_booking(
    self,
    db: AsyncSession,
    *,
    card_id: int,
    tenant_id: int,
    student_id: int,
    schedule_start_at: datetime,
    anchor_start_at: datetime | None,
) -> MembershipCard:
```

实现要求：

1. `lock_student_cards_for_update(db, student_id, tenant_id)`：状态 `IN (ACTIVE, PENDING, FROZEN)`，`ORDER BY id ASC`，`with_for_update()`；其中找到 `card_id`，不存在 → 404/403。
2. 复核 `is_bookable_card()`（复用 T6.3.2 的基础校验）。
3. `validity_days = card.validity_days or (product.validity_days if card.product_id else None)`；缺失 → 400 “期卡缺少有效天数，无法预约，请联系管理员”。
4. 预期窗口锚点：`anchor = anchor_start_at or schedule_start_at`；`expected_valid_from = anchor` 的日期 00:00:00；`expected_expire_at = _calc_expire_at(expected_valid_from, validity_days)`（`membership/service.py:1468-1488`）。
5. 窗口一致性：`schedule_start_at.date()` 必须落在 `[expected_valid_from.date(), expected_expire_at.date()]`，否则 400 “该排期超出此期卡的有效期窗口”。
6. 冲突集合：同学员、同租户、同 `applicable_course_type_code`、`id != card.id`、`valid_from/expire_at` 均非空、状态 `ACTIVE/PENDING/FROZEN`。
7. 重叠判定：`expected_valid_from <= existing.expire_at AND existing.valid_from <= expected_expire_at`；命中 → 409。
8. 不写卡、不写流水、不激活。

**Repository 新增**

- `MembershipCardRepository.get_cards_for_update_by_student(db, student_id, tenant_id, statuses, order_by_id=True)`。
- 不得复用 `get_active_cards_by_student`（`repository.py:201-227` 仅 ACTIVE，会漏 PENDING/FROZEN）。
- `BookingRepository.get_earliest_card_booking_start(db, card_id, tenant_id, statuses=(BOOKED, CHECKED_IN, COMPLETED, NO_SHOW))`：join `course_schedules`，返回该卡已存在的非取消预约中最早的 `start_at`（仅排除 CANCELLED）；无则 None。用于期卡预期窗口锚点。

**BookingService.create_booking 改造**

在现有 `booking/service.py:51-159` 基础上：

1. 预检查（不改变既有顺序）：排期、容量、时间窗口、重复预约。
2. 读取课程：调用 `CourseService.get_course_by_id`（`course/service.py:514-523`）；若返回 DTO 不含 `course_type_code`，新增只读方法 `get_course_validation_snapshot(db, course_id) -> tuple[int, str | None]`，禁止直接查 `Course` 表。
3. 若 `data.membership_card_id`：
   - 先做基础校验（T6.3.2 方法，无锁快路径）；
   - `increment_booked_count`（`booking/service.py:90-92`）；
   - `repo.create(auto_commit=False)` 插入 booking（`:108-110`）；
   - 分支：
     - count：`deduct_credit(..., check_at=schedule.start_at)`（`:129-154`）；
     - period：若卡 `status=PENDING AND valid_from IS NULL`，先查 `get_earliest_card_booking_start` 得到锚点，再 `validate_period_card_booking(..., anchor_start_at=anchor)`（此时已持有 schedule 行锁，符合“schedule → card”顺序）；若卡已 ACTIVE，仅做 D4 排期日校验，不再做预期窗口/冲突检查；
     - unlimited：不调用扣次。
   - 任一步失败 → `db.rollback()`，名额与 booking 一并回滚。
4. 若 `data.membership_card_id is None`：保持现状，不涉及卡。
5. 不修改 `BookingCreate`/`BookingResponse`（`booking/schemas.py:12-59`）。

**deduct_credit 改造**

- 新增可选参数 `check_at: datetime | None = None`；有效期判断使用 `check_at or datetime.now(UTC)`。
- 其他调用方（如未来 AI）不传时保持现状。
- count 分支保持 `FOR UPDATE` + 余额检查（`membership/service.py:1348-1388`）。

**验收映射**：B-4、B-5、B-6、B-7、B-8、B-9、B-22、C-4、C-5、D-4、D-9。

### T6.3.3 期卡首次完成激活（Service 方法 + 手动完成接入）

**改动文件**

- `apps/api/src/app/modules/membership/service.py`
- `apps/api/src/app/modules/booking/service.py`
- `apps/api/src/app/modules/membership/repository.py`（复用 T6.3.2 的卡集锁方法）

**新增方法**

```python
async def activate_period_card_on_completion(
    self,
    db: AsyncSession,
    *,
    card_id: int,
    booking_id: int,
    tenant_id: int,
    schedule_start_at: datetime,
    operator_id: int | None = None,
) -> MembershipCard:
```

实现步骤：

1. 幂等检查：`txn_repo.get_by_idempotency_key(db, f"booking_{booking_id}_period_activate")`；若已存在 → 返回既有卡（`membership/service.py` 现有幂等模式参考 `:244-248`、`:1342-1345`）。
2. `lock_student_cards_for_update(...)`（`id ASC`，含自身），取出目标卡；不存在 → 404。
3. 重检：
   - `card_type != period` → no-op 返回（防御性，调用方应已分支）。
   - `status == ACTIVE` → no-op（非首次）。
   - `status in (EXPIRED, CANCELLED)` → no-op + warning（不阻塞排期终态）。
   - `status == FROZEN` → no-op + warning（PENDING 已在 T6.3.6 禁止冻结；仅兼容历史数据）。
   - `status != PENDING` → 400 “会员卡状态异常，无法激活”。
4. `validity_days = card.validity_days or product.validity_days`；缺失 → 400 “期卡缺少有效天数，无法激活”，异常上抛触发回滚。
5. `valid_from = schedule_start_at` 的日期 00:00:00；`expire_at = _calc_expire_at(valid_from, validity_days)`。
6. 冲突检查：同 T6.3.2 第 5-6 步，排除自身；命中 → 409 “期卡生效区间与已有会员卡重叠，无法激活”。
7. 写入：`card.status=ACTIVE`、`card.valid_from`、`card.expire_at`。
8. 写 ISSUE 流水：`change_amount=0`、`balance_after=0`、`idempotency_key=f"booking_{booking_id}_period_activate"`、`remark="首次完成课程自动激活期卡"`。
9. `db.flush()`，不 commit（由调用方统一 commit）。

**BookingService.complete_booking 改造**

在 `booking/service.py:305-332` 基础上：

1. 保持 `get_by_id_for_update` 与状态重检（`:318-324`）。
2. 读取排期：调用 `ScheduleService.get_schedule_by_id`（`schedule/service.py:504`）获取 `start_at`；若 booking 无 `membership_card_id` 或卡非 period，则跳过。
3. 置 `locked_booking.status = COMPLETED`（`:326`）。
4. 调用 `activate_period_card_on_completion(...)`。
5. 统一 `commit`（`:328`）；激活异常直接上抛，booking 状态随事务回滚。
6. 保持“重复完成 → 400”的既有语义，不改幂等为 no-op（`test_checkin_complete_lock.py:10` AC-6）。

**验收映射**：B-10、B-13、B-20、B-21、D-1、D-5、D-7。

### T6.3.4 Scheduler → BookingService 收口

**改动文件**

- `apps/api/src/app/modules/booking/service.py`
- `apps/api/src/app/modules/booking/repository.py`
- `apps/api/src/app/modules/schedule/service.py`
- `apps/api/src/app/modules/schedule/scheduler.py`
- `apps/api/src/app/modules/schedule/repository.py`（仅在 Service 需要新查询方法时）

**BookingRepository 新增**

- `list_ids_by_schedule(db, schedule_id, statuses: tuple[int, ...]) -> list[int]`：只读，按 `id ASC`。
- `get_by_ids_for_update(db, booking_ids: list[int]) -> list[Booking]`：`WHERE id IN (...) ORDER BY id ASC FOR UPDATE`；带 `tenant_id` 条件（ContextVar 自动注入仍生效）。

**ScheduleService 新增**

- `get_schedule_for_update(db, schedule_id) -> CourseSchedule`：`SELECT ... FOR UPDATE`，带租户约束；不存在 → 404。
- 供 finalize 使用，避免 BookingService 直接使用 `ScheduleRepository` 加锁。

**BookingService.finalize_schedule_bookings**

```python
async def finalize_schedule_bookings(
    self,
    db: AsyncSession,
    schedule_id: int,
    operator_id: int | None = None,
) -> dict:
```

步骤：

1. 读取 booking id 列表（`status IN (BOOKED, CHECKED_IN)`，只读）。
2. 若为空：仍锁定并 FINISHED 排期（保持现状：无预约排期也会结束），commit，返回计数 0。
3. 按 `id ASC` 锁 booking 行。
4. `ScheduleService.get_schedule_for_update` 锁排期。
5. 重检排期：非 NORMAL → no-op（已 FINISHED/CANCELLED），返回 `skipped=True`。
6. 置 `schedule.status = FINISHED`。
7. 逐 booking 重检：
   - `CHECKED_IN` → `COMPLETED`；
   - `BOOKED` → `NO_SHOW`；
   - 其他 → skip。
8. 对 `COMPLETED` 与 `NO_SHOW`（D5）且带 period 卡的 booking 调用 `activate_period_card_on_completion(...)`。
9. `commit` 一次；任一步异常 → 不 commit，异常上抛。
10. 返回：`{"schedule_id", "completed_count", "no_show_count", "skipped_count", "activated_count"}`。

**schedule/scheduler.py 改造**

- 删除 `update(Booking)` 两段 bulk（`schedule/scheduler.py:93-109`）与直接赋值 `schedule.status`（`:90-91`）。
- 保留候选排期查询（`:73-79`）与逐租户 ContextVar（`:65-67`）。
- 对每个排期：
  ```python
  async with SessionLocal() as db:
      await booking_service.finalize_schedule_bookings(db, schedule.id)
  ```
  或复用同一租户 session 逐排期调用；基线选择“每排期一个 session”，避免单排期失败拖累其他排期。
- 单排期异常记录 `tenant_id/schedule_id` 后继续；不中断其他租户。
- 保留 `AUTO_FINISH_ENABLED` 开关（`config.py:61`）。

**验收映射**：B-11、B-12、A-4、D-2、D-8。

### T6.3.5 取消回补按卡类型分支

**改动文件**

- `apps/api/src/app/modules/membership/service.py`
- 调用方无需改签名：`booking/service.py:252-267`、`schedule/service.py:359-378`

**步骤**

1. `restore_credit` 在 `get_card_with_lock` 之后、`used_credits <= 0` 检查之前加入：
   ```python
   if card.card_type != CardType.COUNT.value:
       return card
   ```
2. 次卡逻辑保持 `used_credits -= 1` 与 RESTORE 流水（`membership/service.py:1430-1448`）。
3. 期卡/无限卡：不写流水、不改 `used_credits`、不抛 400。
4. 不改变调用方幂等键：
   - 取消预约 `booking_{booking.id}_restore`（`booking/service.py:254`）；
   - 取消排期 `schedule_cancel_{booking.id}_{schedule_id}`（`schedule/service.py:361`）。

**边界**：`cancel_schedule` 只处理 BOOKED（`schedule/service.py:340-347`）；CHECKED_IN 不在本 Feature 扩大（P17/C-15）。

**验收映射**：B-14、B-15、E-2。

### T6.3.6 冻结、过期扫描、90 天未激活作废

**改动文件**

- `apps/api/src/app/modules/membership/service.py`
- `apps/api/src/app/modules/membership/scheduler.py`
- `apps/api/src/app/modules/membership/repository.py`
- `apps/api/src/app/core/config.py`
- `apps/api/src/app/main.py`

**freeze_card**

- 在 `membership/service.py:624-632` 之后新增：
  ```python
  if card.status == CardStatus.PENDING.value:
      raise HTTPException(status_code=400, detail="未激活卡不可冻结")
  ```
- 失败时不得修改 `frozen_*` 或 `expire_at`（现有冻结顺延逻辑 `:655-660` 不应执行）。

**过期扫描**

- `_expire_cards_in_transaction`（`membership/scheduler.py:51-103`）与 `auto_expire_membership_cards`（`:259-357`）查询改为：
  ```python
  MembershipCard.expire_at < now,
  MembershipCard.expire_at.isnot(None),
  MembershipCard.status.in_([CardStatus.ACTIVE.value, CardStatus.PENDING.value]),
  ```
- 逐卡处理前 `SELECT ... FOR UPDATE` 并重检状态；单卡失败隔离（沿用现有 `try/except`）。
- 次卡剩余次数清零逻辑不变（`:73-85`、`:307-330`）；期卡 `total_credits is None`，只写 `change_amount=0` 的 EXPIRE。
- `auto_activate_membership_cards` 的 `expire_at` 计算改为优先 `card.validity_days`，回退 `product.validity_days`（`membership/scheduler.py:206-227`），避免快照与产品变更不一致。

**90 天 PENDING 期卡作废**

配置（`core/config.py:61-66` 附近）：

```python
PENDING_CARD_CANCEL_ENABLED: bool = True
PENDING_CARD_CANCEL_DAYS: int = 90
```

新增 Scheduler `auto_cancel_pending_membership_cards()`：

1. 若 `not settings.PENDING_CARD_CANCEL_ENABLED` → return。
2. 遍历 ACTIVE 租户，`set_tenant_id(tenant_id)`，每租户一个 `SessionLocal`。
3. 查询：
   - `card_type == "period"`
   - `status == PENDING`
   - `created_at < now - timedelta(days=settings.PENDING_CARD_CANCEL_DAYS)`
   - `NOT EXISTS` 关联该卡的 `booking.status IN (COMPLETED, NO_SHOW)`（`booking.membership_card_id == card.id`）
4. 逐卡 `FOR UPDATE`，重检 PENDING。
5. 置 `CANCELLED`、`cancelled_at=now`、`cancelled_reason="超期未激活（90天）"`。
6. 写 EXPIRE 流水（`change_amount=0`，`remark="PENDING期卡超期未激活，自动作废"`）。
7. 单卡异常记录继续；租户异常回滚该租户；`finally set_tenant_id(None)`。
8. `main.py` 注册任务：`scheduler.add_job(auto_cancel_pending_membership_cards, "interval", minutes=1440, id="auto_cancel_pending_membership_cards", replace_existing=True)`；基线不新增 interval 配置。

**验收映射**：B-16、B-17、B-18、B-19、C-7、C-8、D-6。

### T6.3.7 测试与回归

**新增单元测试**：`apps/api/tests/unit/test_membership_card_state_machine.py`

- `test_is_period_pending_bookable`：`PENDING + valid_from=NULL` → True；`PENDING + valid_from=未来` → False；ACTIVE/FROZEN/EXPIRED/CANCELLED 分支。
- `test_calc_expected_interval_inclusive`：`validity_days=3`，排期日 2026-10-22 → `valid_from=2026-10-22 00:00:00`、`expire_at=2026-10-24 23:59:59`。
- `test_interval_overlap_closed`：边界相接（`a.end == b.start`）判重叠；完全不接判不重叠。
- `test_bookable_on_expire_date`：排期日 = `expire_at` 当天 → True；次日 → False。

**新增集成测试**

| 文件 | 用例 |
|------|------|
| `apps/api/tests/integration/test_membership_period_card_lifecycle.py` | `test_issue_period_card_pending_without_validity`、`test_issue_period_card_requires_validity_days`、`test_issue_count_card_unchanged`、`test_issue_card_forbidden_for_non_admin`、`test_freeze_pending_rejected` |
| `apps/api/tests/integration/test_period_card_booking_validation.py` | `test_book_period_card_no_deduct_no_activate`、`test_book_count_card_deducts_once`、`test_expected_validity_conflict_rejected`、`test_expected_validity_no_conflict_allows`、`test_booking_on_expire_date_boundary`、`test_pending_with_future_valid_from_rejected`、`test_d9_pending_bookable`、`test_other_student_card_rejected`、`test_cross_tenant_card_rejected`、`test_period_card_course_applicability`、`test_period_card_booking_window_anchor` |
| `apps/api/tests/integration/test_period_card_activation_concurrency.py` | `test_manual_complete_activates_once`、`test_repeat_complete_rejected`、`test_concurrent_complete_activates_once`、`test_activation_idempotency_key`、`test_activation_conflict_rolls_back`、`test_concurrent_finalize_idempotent`、`test_lock_order_no_deadlock`、`test_period_card_missing_validity_days_fails_closed` |
| `apps/api/tests/integration/test_membership_card_deduct_lifecycle.py` | `test_count_card_complete_no_extra_deduct`、`test_period_card_cancel_no_restore`、`test_cancel_schedule_period_noop_count_restore` |
| `apps/api/tests/integration/test_booking_card_concurrency.py` | `test_concurrent_cancel_once`、`test_concurrent_deduct_no_overdraft`、`test_concurrent_period_booking_serialized` |
| `apps/api/tests/integration/test_membership_card_expiry_jobs.py` | `test_auto_finish_activates_period_card`、`test_auto_finish_no_show_activates_period_card`、`test_expire_scan_includes_pending`、`test_pending_period_card_cancelled_after_90_days`、`test_pending_with_completed_booking_not_cancelled`、`test_jobs_idempotent_on_second_run`、`test_pending_cancel_tenant_isolation` |
| `apps/api/tests/integration/test_booking_card_authorization.py` | `test_booking_forbidden_for_non_student`、`test_complete_forbidden_without_permission`、`test_other_student_card_rejected`（可与上表合并） |

测试基建要求：

- 复用 F2.3/F2.4 的事件循环隔离模式：session 级 fixture 只返回纯数据 dict，function 级 `local_db` 独立 engine（`test_checkin_complete_lock.py:76-168`、`test_cancel_schedule_rollback.py:154-242`）。
- 并发用例使用 `live_server` 真实 Uvicorn；`SELECT ... FOR UPDATE` 在 PostgreSQL 层面生效。
- 直接构造“期卡 + 排期 + booking”数据时，必须显式 `set_tenant_id` 并清理，避免污染种子数据。
- 90 天任务用例通过插入 `created_at=now-91d` 的卡触发；不修改系统时间。

**回归命令**

```bash
cd apps/api
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_checkin_complete_lock.py -v
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_cancel_schedule_rollback.py -v
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_fk_membership_card.py -v
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_order_fk_membership_card.py -v
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_status_check_constraints.py -v
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_schedule_create_concurrency.py -v
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_ownership.py -v
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_rbac_enforcement.py tests/integration/test_rbac.py -v
PYTHONPATH=src .venv/bin/python -m pytest tests/test_scheduler_tenant_isolation.py -v
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_unfreeze_lock_ordering.py -v
```

## 4. 事务边界与行锁顺序

### 4.1 事务边界

| 流程 | 共享同一事务的写操作 | commit 位置 |
|------|----------------------|-------------|
| 创建预约 | 名额递增 + booking INSERT + 卡校验/扣次 + 流水 | `BookingService.create_booking`（`booking/service.py:155`） |
| 取消预约 | booking 状态 + 名额递减 + 卡回补 + 流水 | `BookingService._do_cancel_booking`（`:269`） |
| 手动完成 | booking 状态 + 期卡激活 + ISSUE 流水 | `BookingService.complete_booking`（`:328`） |
| 排期自动结束 | schedule FINISHED + booking 终态 + 期卡激活 + ISSUE | `BookingService.finalize_schedule_bookings` |
| 取消排期 | schedule 状态 + 多 booking 取消 + 名额递减 + 次卡回补 | `ScheduleService.cancel_schedule`（`schedule/service.py:387`） |
| 发卡 | 卡 INSERT + ISSUE 流水 | Router（`membership/router.py:203`） |
| 过期/作废任务 | 逐卡状态 + EXPIRE 流水 | Scheduler 逐租户（`membership/scheduler.py:245` 等） |

### 4.2 锁顺序

| 流程 | 加锁顺序 | 说明 |
|------|----------|------|
| 创建预约 | schedule（容量递增）→ booking（INSERT）→ membership card（扣次/期卡校验） | 创建路径无既有 booking 行可先锁；保持现有 `schedule → booking → card` |
| 手动完成 | booking → membership card | 排期只读，不加锁；锁顺序不逆序 |
| 自动 finalize | booking（`id ASC`）→ schedule → membership card（`id ASC`） | 严格符合 `booking → schedule → card` |
| 取消预约 | booking → membership card | `booking/service.py:214` → `:252-267` |
| 取消排期 | membership card（逐 booking）→ schedule 更新 | **现状未锁 booking、未先锁 schedule**，为 F2.4 既有实现；见 C-15，不在本 Feature 重写 |
| 发卡 | membership card（学员卡集，`id ASC`） | `membership/service.py:265-278` |
| 冻结/激活/过期/作废 | membership card（单卡） | `get_card_with_lock`（`:482-506`） |
| 90 天作废 | membership card（单卡） | 逐卡 `FOR UPDATE` + 状态重检 |

**死锁规避**：所有多卡场景统一 `ORDER BY id ASC`；finalize 必须先锁 booking 再锁 schedule；create 必须先锁 schedule 再锁 card；任何新代码不得反向。

## 5. 幂等键与状态重检

### 5.1 幂等键

| 操作 | 幂等键 | 证据/落点 |
|------|--------|-----------|
| 次卡预扣 | `booking_{booking.id}_deduct` | `booking/service.py:131` |
| 取消预约回补 | `booking_{booking.id}_restore` | `booking/service.py:254` |
| 取消排期回补 | `schedule_cancel_{booking.id}_{schedule_id}` | `schedule/service.py:361` |
| 期卡首次激活 | `booking_{booking.id}_period_activate` | 新增；写 ISSUE 流水 |
| 发卡 | 现有 Service 支持，但 Router 未传 | `membership/service.py:234-248`、`router.py:198-205`（C-16） |
| 过期/90 天作废 | 无键，状态重检 | 重复执行 no-op |

流水唯一约束：`idempotency_key` 唯一 + 部分唯一索引（`membership/models.py:294-311`）。

### 5.2 状态重检

| 对象 | 重检点 |
|------|--------|
| booking | 拿到 `FOR UPDATE` 后必须重读 `status`，再决定取消/签到/完成/finalize |
| schedule | finalize 锁排期后重检 NORMAL；非 NORMAL 直接 no-op |
| membership card | 激活/冻结/过期/回补/扣次均在锁后重读 `status`、`used_credits`、`valid_from/expire_at` |
| 幂等流水 | 写流水前按 `idempotency_key` 查询；存在则返回既有结果 |

## 6. Scheduler → BookingService 收口方案

### 6.1 改动前后

**改动前**（违反分层）：

```text
schedule/scheduler.py
  ├─ schedule.status = FINISHED
  ├─ update(Booking).values(status=COMPLETED)
  ├─ update(Booking).values(status=NO_SHOW)
  └─ db.commit()
```

证据：`schedule/scheduler.py:90-111`。

**改动后**：

```text
schedule/scheduler.py
  ├─ 逐租户查询候选排期（只读）
  ├─ 逐排期调用 BookingService.finalize_schedule_bookings
  └─ 异常隔离 + 日志

BookingService.finalize_schedule_bookings
  ├─ 锁 booking（id ASC）
  ├─ 锁 schedule 并重检
  ├─ schedule.status = FINISHED
  ├─ CHECKED_IN → COMPLETED / BOOKED → NO_SHOW
  ├─ 期卡首次激活
  └─ commit
```

### 6.2 失败与重试

- 单排期失败：整排期事务回滚，Scheduler 记录 `tenant_id/schedule_id/error`，继续处理其他排期。
- 下一轮任务会重新选中该排期（仍 NORMAL），实现最终一致。
- 若因期卡缺 `validity_days` 持续失败：属于部署/数据错误，必须在发布前通过 SQL 检查拦截；运行期持续告警。
- 不在 Scheduler 内做“跳过卡继续完成 booking”，避免半状态。

## 7. DB 迁移与索引评估

### 7.1 为什么需要迁移（证据）

- 期卡发卡允许显式 `validity_days`（`membership/schemas.py:114-131`），但 `MembershipCard` 没有该字段（`membership/models.py:146-239`）。
- 首次完成激活发生在发卡之后，必须使用“发卡时确定的天数”；若只读 `product.validity_days`，产品后续被修改会导致卡条款漂移；若发卡时 `product_id` 为空或显式天数覆盖产品值，则完全无法还原。
- 因此新增可空列 `validity_days` 是数据正确性要求，不是性能优化。

### 7.2 迁移内容

文件：`apps/api/alembic/versions/<new_revision>_add_membership_card_validity_days.py`

```python
def upgrade() -> None:
    op.add_column(
        "membership_cards",
        sa.Column(
            "validity_days",
            sa.SmallInteger(),
            nullable=True,
            comment="发卡时确定的有效天数快照（期卡激活用）",
        ),
    )
    # 回填 1：产品优先
    op.execute("""
        UPDATE membership_cards c
        SET validity_days = p.validity_days
        FROM membership_card_products p
        WHERE c.product_id = p.id
          AND c.card_type = 'period'
          AND c.validity_days IS NULL
          AND p.validity_days IS NOT NULL
    """)
    # 回填 2：日期差反推（含首尾）
    op.execute("""
        UPDATE membership_cards
        SET validity_days = (expire_at::date - valid_from::date) + 1
        WHERE card_type = 'period'
          AND validity_days IS NULL
          AND valid_from IS NOT NULL
          AND expire_at IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column("membership_cards", "validity_days")
```

- 不加 `NOT NULL`：历史数据可能无法回填；激活时缺失则 fail-closed（400）。
- 不在迁移中修改卡状态或有效期，避免不可逆业务变更。

### 7.3 索引评估

| 查询 | 现有索引 | 结论 |
|------|----------|------|
| 过期扫描 `tenant_id + status IN (ACTIVE,PENDING) + expire_at < now` | `idx_cards_expire(tenant_id, expire_at, status)`（`membership/models.py:234`） | 可用：tenant 等值 + expire_at 范围；status 作为索引内过滤。基线不新增索引 |
| 90 天扫描 `tenant_id + status=PENDING + card_type=period + created_at < cutoff` | 无 `created_at` 索引；`idx_cards_student(tenant_id, student_id, status)` 不覆盖 | 基线不新增；先在生产数据量上 `EXPLAIN (ANALYZE, BUFFERS)` 评估。若出现全表扫描且表规模大，再加部分索引：`CREATE INDEX idx_cards_pending_created ON membership_cards (tenant_id, created_at) WHERE status = 0 AND card_type = 'period'` |
| 卡集锁 `tenant_id + student_id + status IN (...) ORDER BY id` | `idx_cards_student(tenant_id, student_id, status)` | 可用；排序 `id` 为回表排序，基线接受 |
| 流水幂等键 | 唯一 + 部分唯一索引（`membership/models.py:302-312`） | 已覆盖 |

**结论**：本 Feature 只新增 1 列，不新增索引；若 90 天任务 `EXPLAIN` 证明需要，再单独评估（不计入基线交付）。

## 8. 测试计划

见 T6.3.7。补充要求：

1. 单测覆盖纯函数：`is_bookable_card`、`expected_interval`、`_calc_expire_at`、区间重叠边界。
2. 集成测试覆盖 HTTP + DB 双断言；错误路径断言“无 booking/无流水/名额未变”。
3. 并发测试使用 `live_server`，验证一成一败、流水唯一、无死锁。
4. 任务测试通过直接调用 job 函数 + `local_db` 构造数据；不依赖真实等待 5 分钟。
5. 回归测试按文件单独执行，规避已知跨文件 event loop 污染（参考 F5.4 的实施记录 `docs/features/F5.4-cleanup-ai-tools/implementation-plan.md:44-45`）。
6. 所有测试结果写入 `acceptance.md` 的验收记录表；未执行前保持 `PLAN_NOT_RUN`。

## 9. 回滚预案

### 9.1 代码回滚

1. 先关闭新增任务：`PENDING_CARD_CANCEL_ENABLED=false`（配置热更新/重启）。
2. 回滚后端代码到 F6.3 之前版本。
3. 保留 `membership_cards.validity_days` 列（旧代码不读取，可空，无影响）。
4. 不单独回滚 `schedule/scheduler.py`：旧代码会恢复 bulk update，导致期卡不激活；必须整 Feature 回滚。

### 9.2 迁移回滚

- `alembic downgrade -1` 会删除 `validity_days`。
- 若已有 F6.3 发卡产生的 `PENDING + valid_from=NULL + expire_at=NULL` 期卡，回滚前必须：
  - 方案 A（推荐）：保留列，仅回滚代码（向前修复优先），避免数据丢失；
  - 方案 B：先把这些卡作废/激活并导出 `card_id → validity_days` 映射，再 downgrade；
  - 方案 C：downgrade 后这些卡无法被旧代码激活（旧 `issue_card` 不会产生，`auto_activate` 查 `valid_from <= now` 不命中 NULL），会成为永久 PENDING，必须人工处理。
- 因此生产回滚优先“代码回滚 + 保留列”，不轻易 downgrade。

### 9.3 数据修复

- 若期卡在激活时因冲突长期失败：按 `card_id` 定位冲突卡，人工确认后冻结/作废其中一张，下一轮 finalize 重试。
- 若 90 天任务误作废：从 `membership_card_transactions` 的 EXPIRE 流水与 `cancelled_reason` 定位，人工恢复需产品/运营审批；本 Feature 不提供自动恢复端点。

## 10. Conflict（文档 vs 真实代码）

| ID | Conflict | Evidence | Impact | Recommendation |
|----|----------|----------|--------|----------------|
| C-1 | Backlog DoR 称“无 DB 结构变更即可实施”，但期卡激活需要发卡时的 `validity_days` | `docs/delivery/feature-backlog.md:462`；`membership/schemas.py:114-131`；`membership/models.py:146-239` 无该字段 | 不加快照则激活天数不可靠，产品变更或显式入参会导致错误有效期 | 新增可空列 + 回填；同步修订 DoR 表述为“仅新增 1 个可空列，无破坏性变更” |
| C-2 | D4“PENDING 不可预约”与 D9“发卡即 PENDING、预约不扣次”字面冲突 | `open-decisions.md:34-38`；`business-rules.md:50-55` | 若一刀切拒绝 PENDING，D9 期卡永远无法预约 | 采用判定函数：`PENDING + valid_from IS NULL + period` 可预约；有生效日的 PENDING 不可预约 |
| C-3 | 期卡发卡当前立即 ACTIVE 且有有效期 | `membership/service.py:397-429` | 与 D9 冲突，期卡在首次完成前就开始计时 | period 分支强制 PENDING + 空有效期；非 period 不变 |
| C-4 | `deduct_credit` 要求 ACTIVE 且用 `now` 校验 | `membership/service.py:1348-1363` | 期卡无法预约；次卡可能在到期后预约未来课程 | 期卡不走扣次；`deduct_credit` 增加 `check_at`，创建预约传 `schedule.start_at` |
| C-5 | `restore_credit` 无卡类型分支 | `membership/service.py:1405-1449` | 期卡取消会 400，导致取消预约/取消排期整体回滚 | period/unlimited 在锁后直接 no-op |
| C-6 | `complete_booking` 不触碰卡 | `booking/service.py:305-332` | D1/D9 无实现 | 在同一事务内调用期卡激活方法 |
| C-7 | Scheduler 直接 bulk update 业务状态 | `schedule/scheduler.py:90-111` | 违反分层，期卡不激活 | 收口到 `BookingService.finalize_schedule_bookings` |
| C-8 | 文档写“排期 COMPLETED”，真实枚举无该值 | `open-decisions.md:16`、`business-rules.md:30`；`schedule/models.py:12-15`；`feature-backlog.md:439` 已纠正为 BookingStatus | 误加枚举会导致状态约束/查询错乱 | 统一使用 booking `COMPLETED/NO_SHOW` + schedule `FINISHED` |
| C-9 | `freeze_card` 未拒绝 PENDING | `membership/service.py:624-632` | 未激活卡被冻结并顺延有效期 | 新增 PENDING 400 |
| C-10 | 过期扫描仅 ACTIVE | `membership/scheduler.py:283-289` | 带 `expire_at` 的 PENDING 卡永久滞留 | 扩展为 `ACTIVE/PENDING` + `expire_at IS NOT NULL` |
| C-11 | `auto_activate` 会把带 `valid_from` 的 PENDING 直接激活 | `membership/scheduler.py:136-141,203` | 与 D9“首次完成激活”混淆 | 保留旧数据兼容；新 D9 卡 `valid_from=NULL` 不会被命中；在文档与注释中固定语义 |
| C-12 | 无 90 天任务与配置 | `main.py:77-142`；`config.py:61-66` | R-B7 a) 缺失 | 新增任务 + `PENDING_CARD_CANCEL_DAYS` |
| C-13 | 冲突检查只取 ACTIVE 卡 | `membership/repository.py:201-227` | 漏判 PENDING/FROZEN 重叠 | 新增 `get_cards_for_update_by_student`，状态含 ACTIVE/PENDING/FROZEN |
| C-14 | 文档锁顺序写 booking→schedule→card，创建路径实际 schedule→booking→card | `transaction.md:22-25`；`booking/service.py:90-154` | 创建时无既有 booking 行可先锁 | 保留 `schedule → booking → card`；finalize/complete 严格遵守 booking 先锁；见 4.2 |
| C-15 | 取消排期未锁 booking、只处理 BOOKED | `schedule/service.py:340-378` | 与 finalize 并发时存在竞态；CHECKED_IN 不回补 | 本 Feature 不重写 F2.4；记录为 P17/R7，后续独立 Feature |
| C-16 | 发卡 Service 支持幂等键但 Router 未传 | `membership/service.py:234-248`；`router.py:198-205` | 重复点击生成多张 PENDING 卡 | 不在本 Feature 扩接口；管理端防抖 + 后续补 `Idempotency-Key` |
| C-17 | 小程序把所有 PENDING 卡置灰 | `apps/miniapp/src/pages/student/booking-confirm/index.vue:277-286` | 后端支持但 UI 不可选 | 运行时验收走 API；UI 归 F6.10/F6.11 |
| C-18 | `POST /bookings/` 带尾斜杠，违反 contracts “集合端点不加尾斜杠” | `booking/router.py:22`；`architecture/contracts.md` | 与契约规范不一致，但属既有契约 | 记录不顺手改；避免本 Feature 引入前后端契约破坏 |
| C-19 | 既有测试要求“重复完成返回 400”，与“激活幂等”看似冲突 | `test_checkin_complete_lock.py:10`（AC-6） | 若改为 no-op 会回归失败 | 保持 400；激活幂等由 booking 行锁 + 卡 ACTIVE 重检 + ISSUE 幂等键保证 |
| C-20 | 预约链路未校验卡归属/课程适用性 | `booking/service.py:51-159`；`membership/service.py:1348-1368` | 同租户盗用他人卡、使用不适用的卡 | T6.3.2 增加 403/400 校验；属于安全前置，不新增端点 |
| C-21 | 无限卡 `deduct_credit` 写 `change_amount=-1` 但不改 `used_credits` | `membership/service.py:1365-1368,1390-1401` | 流水与余额不一致 | 期卡/无限卡不调用扣次；本 Feature 不改流水表结构 |
| C-22 | `BookingService` 既有直接使用 `ScheduleRepository` | `booking/service.py:47-48` | 与“跨模块只调 Service”有偏差 | 新增读取改走 `ScheduleService`/`CourseService`；既有偏差记录，不在本 Feature 大重构 |
| C-23 | D9 只要求“按排期日 + validity_days 算预期有效期”，未规定同一张 PENDING 期卡多次预约的窗口一致性 | `business-rules.md:51-52`；真实代码无卡-预约绑定窗口字段 | 短有效期卡（如 7 天）可能先约 A 日、再约 A+10 日，首次完成激活后第二笔落在有效期外 | T6.3.2 增加锚点：取该卡最早非取消预约的排期日，后续预约必须落在 `锚点 + validity_days - 1` 内；不新增字段 |

## 11. UNKNOWN

1. **UNKNOWN-1 激活冲突策略**：并发 PENDING 期卡导致激活冲突时，基线选择 fail-closed（回滚、保 PENDING、下轮重试）。需产品确认是否改为“booking 完成 + 卡作废/人工处理”。
2. **UNKNOWN-2 90 天计时起点**：按 `created_at` 还是首次预约/最后完成时间；本文按 `created_at`。
3. **UNKNOWN-3 回填口径**：产品天数与日期差反推冲突时以产品优先；需 database-engineer 在生产数据上先统计。
4. **UNKNOWN-4 NO_SHOW 激活**：D5 文字支持“课开即扣/激活”，本文按“是”；若产品否认，需要调整 finalize。
5. **UNKNOWN-5 `max_weekly_usage`**：当前扣次未校验（`membership/service.py:1328-1403`），本 Feature 不实现；需确认是否遗漏。
6. **UNKNOWN-6 旧 PENDING 期卡**：带 `valid_from` 的历史卡是否继续由 `auto_activate` 直接激活；本文建议保留兼容。
7. **UNKNOWN-7 生产迁移窗口与数据量**：未读取具体 Alembic 链路；需 database-engineer 在预发执行 `EXPLAIN` 与回填统计。
8. **UNKNOWN-8 课程类型口径**：`Course.course_type_code` 为空时，卡 `applicable_course_type_code` 的匹配语义（拒绝还是放行）；本文建议：卡有限制而课程无类型 → 拒绝，避免绕过。
9. **UNKNOWN-9 激活基准日**：本文按 `schedule.start_at` 的日期，而非实际完成时间；符合 D9“排期日”，但需产品确认延迟完成场景。
10. **UNKNOWN-10 90 天任务执行频率**：本文固定 1440 分钟；若运营要求更快，需要新增 interval 配置。
11. **UNKNOWN-11 period 下 `valid_from` 入参**：本文建议忽略并记录 warning（避免管理端默认值导致 400），但需确认管理端是否总是发送该字段；若要求严格，改为 400 并同步前端。

