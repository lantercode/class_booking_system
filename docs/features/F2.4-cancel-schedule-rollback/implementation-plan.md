# F2.4 — cancel_schedule 回补失败回滚 · 实施方案

> Feature ID：F2.4
> 作者：backend-engineer
> 日期：2026-09-28
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

`ScheduleService.cancel_schedule` 用"外层 try/except + 末尾 commit"模式吞掉 booking 处理异常 → 失败 booking 的部分状态被无条件提交：

1. **外层 try/except 吞异常**：[service.py:272-299](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L272-299)（修复前）：`for booking in booking_list: try: ... except Exception as e: failed_bookings.append(...)` —— 异常被吞 → 循环继续 → 末尾 `await db.commit()` 提交已变更的 `booking.status=CANCELLED` / `booked_count-=1` 但 `restore_credit` 未执行。
2. **内层 try/except 已 raise 但被外层接住**：[service.py:283-293](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L283-293)（修复前）：`try: await restore_credit(...) except Exception as e: logger.error(...); raise` —— raise 出去后被外层 except 接住 → 失败 booking 被记到 `failed_bookings` 但循环继续。

**对照**：`BookingService._do_cancel_booking`（[booking/service.py:198-272](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L198-272)）已是正确事务模式——`restore_credit` 失败 → `raise BusinessException(f"会员卡恢复次数失败，取消预约操作已撤销: {e}", code=500)` → 不 commit → session 回滚。本 Feature 让 `cancel_schedule` 与之同构。

## 已核查的代码事实（Evidence）

| 事实 | 证据 |
|------|------|
| router 仅消费 `total_bookings` / `success_count` | [router.py:192-193](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/router.py#L192-193)：`if result["total_bookings"] > 0: msg = f"...{result['success_count']}/{result['total_bookings']}..."` —— 不读 `failed_bookings` / `failed_count`，故返回 dict 字段集合保持兼容即可 |
| `MembershipCardService.restore_credit` 自带幂等键 | [membership/service.py:1399-1443](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1399-1443)：`idempotency_key` 查 DB txn；事务回滚后 INSERT 的 txn 也回滚 → 幂等键回到初始状态，下次重试不会因幂等短路而漏回补 |
| `ScheduleRepository.decrement_booked_count` 已含 FOR UPDATE | [repository.py:197-220](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/repository.py#L197-220)：`select(CourseSchedule).where(...).with_for_update()` → 排期行锁 |
| `BookingRepository.search` 返回 `(list, total)` | [booking/repository.py:22-98](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L22-98)：签名 `-> tuple[list[Booking], int]` |
| `BusinessException.code` 即 HTTP 状态码 | [exceptions.py:28-30](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/exceptions.py#L28-30)：`def __init__(self, msg="业务错误", code=500, ...)`，全局异常处理器用 `code` 作 HTTP 状态码 |
| `_do_cancel_booking` 的内层 except 范式 | [booking/service.py:254-266](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L254-266)：`try: await restore_credit(...) except Exception as e: logger.error(...); raise BusinessException(f"会员卡恢复次数失败，取消预约操作已撤销: {e}", code=500)` |
| Service 签名不变 | `cancel_schedule(db, schedule_id, cancel_reason, operator_id) -> dict[str, Any]` —— Router 调用不变 |
| 端点装饰器 `@require_permissions("schedule:cancel")` 不变 | [router.py:176](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/router.py#L176) |
| `BookingStatus` 枚举 | [booking/models.py:12-17](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L12-17)：`BOOKED=1 / CANCELLED=2 / CHECKED_IN=3 / COMPLETED=4 / NO_SHOW=5` |
| `ScheduleStatus` 枚举 | [schedule/models.py:12-15](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/models.py#L12-15)：`NORMAL=1 / CANCELLED=2 / FINISHED=3` |

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/modules/schedule/service.py` | `cancel_schedule`（L231-322）方法体重构：移除外层 try/except；内层 except 改 raise `BusinessException(500)`；移除 `success_count` / `failed_bookings` 累加；保留返回 dict 字段集合兼容；`bookings[0]` → `bookings, _` 解构；补 docstring |
| 2 | `apps/api/tests/integration/test_cancel_schedule_rollback.py` | 新建，12 用例覆盖 AC-1 ~ AC-7 + 补充场景（FINISHED 400 / 不存在 404 / 学员越权 403） |

**不在改动范围**：router / repository / models / schemas / OpenAPI / 前端 / MCP / DB 结构 / migration / Redis。

## Exact Fix

### `cancel_schedule`（service.py:231-330，修复后）

```python
async def cancel_schedule(
    self,
    db: AsyncSession,
    schedule_id: int,
    cancel_reason: str,
    operator_id: int,
) -> dict[str, Any]:
    """取消排期(含学员预约处理)

    事务边界：本方法持有整个事务。任一 booking 处理失败（含
    ``MembershipCardService.restore_credit`` 失败）都直接 raise，
    ``db.commit()`` 永不执行，AsyncSession 由 FastAPI 依赖清理时被动回滚，
    全部 booking 状态变更、``decrement_booked_count``、schedule 状态变更
    一并回滚，保证数据一致。与 ``BookingService._do_cancel_booking`` 同构。
    """
    logger.warning(
        f"[ScheduleService] 取消排期: schedule_id={schedule_id}, reason={cancel_reason}"
    )

    schedule = await self.repo.get_by_id(db, schedule_id)
    if not schedule:
        raise NotFoundException("排期不存在")

    if schedule.status == ScheduleStatus.CANCELLED.value:
        raise BusinessException("排期已取消", code=400)

    if schedule.status == ScheduleStatus.FINISHED.value:
        raise BusinessException("排期已完成，无法取消", code=400)

    from app.modules.booking.models import BookingStatus
    from app.modules.booking.repository import BookingRepository
    from app.modules.membership.service import MembershipCardService

    booking_repo = BookingRepository()
    membership_card_service = MembershipCardService()

    bookings, _ = await booking_repo.search(
        db,
        schedule_id=schedule_id,
        status=BookingStatus.BOOKED.value,
        page=1,
        page_size=1000,
    )
    total_bookings = len(bookings)

    # 逐个处理预约取消 + 课时回补。
    # 任一失败 → raise → db.commit() 永不执行 → AsyncSession 被动回滚
    # → 已变更的 booking 状态、decrement_booked_count、schedule 状态全部回滚。
    for booking in bookings:
        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = datetime.now(UTC)
        booking.cancelled_reason = f"老师取消课程: {cancel_reason}"

        await self.repo.decrement_booked_count(db, schedule_id)

        if booking.membership_card_id:
            tenant_id = booking.tenant_id
            idempotency_key = f"schedule_cancel_{booking.id}_{schedule_id}"
            try:
                await membership_card_service.restore_credit(
                    db,
                    card_id=booking.membership_card_id,
                    tenant_id=tenant_id,
                    booking_id=booking.id,
                    idempotency_key=idempotency_key,
                )
            except Exception as e:
                logger.error(
                    f"[ScheduleService] 取消排期时会员卡恢复次数失败 "
                    f"booking_id={booking.id} card_id={booking.membership_card_id}: {e}"
                )
                raise BusinessException(
                    f"会员卡恢复次数失败，取消排期操作已撤销: {e}",
                    code=500,
                )

    update_data = {
        "status": ScheduleStatus.CANCELLED.value,
        "cancel_reason": cancel_reason,
        "cancelled_by": operator_id,
        "cancelled_at": datetime.now(UTC),
    }
    schedule = await self.repo.update(db, schedule_id, update_data)
    await db.commit()
    await db.refresh(schedule)

    logger.warning(
        f"[ScheduleService] ✅ 排期已取消: id={schedule_id}, "
        f"total_bookings={total_bookings}, all_restored=True"
    )

    # 返回字段集合保持与既有契约一致（router 仅消费 total_bookings / success_count）。
    # 事务回滚路径不会执行到这里；正常路径下 success_count == total_bookings。
    return {
        "schedule_id": schedule_id,
        "total_bookings": total_bookings,
        "success_count": total_bookings,
        "failed_count": 0,
        "failed_bookings": [],
    }
```

## 关键决策记录（Decision）

| # | 决策 | 理由 |
|---|------|------|
| D1 | 移除外层 try/except，让异常直接传播 | 修复前外层 except 吞异常导致脏提交；事务边界在 Service，异常传播触发 session 回滚是 SQLAlchemy 的标准事务模式 |
| D2 | 内层 try/except 改 `raise BusinessException(500)` 而非裸 `raise` | 与 `_do_cancel_booking` 同构；统一信封 msg"会员卡恢复次数失败，取消排期操作已撤销"对用户可理解；`code=500` 表示这是事务撤销（不是用户输入错误）；原始异常 `e` 拼接到 msg（已被全局异常处理器透传，但不回显 traceback） |
| D3 | 保留返回 dict 字段集合（`schedule_id` / `total_bookings` / `success_count` / `failed_count` / `failed_bookings`） | router L192-193 消费 `total_bookings` / `success_count`；保持字段集合不变 → router 无需改动；正常路径下 `success_count == total_bookings`，`failed_count == 0`，`failed_bookings == []`；事务回滚路径不到达 return |
| D4 | 移除 `success_count` / `failed_bookings` 累加逻辑 | 事务回滚后这些计数无意义（异常路径不到达 return）；正常路径下值固定（全部成功），无需累加 |
| D5 | `bookings = await ...; booking_list = bookings[0]` → `bookings, _ = await ...` | `BookingRepository.search` 返回 `(list, total)` tuple；解构比 `[0]` 取首元素语义清晰；零行为变更 |
| D6 | 不改 Router / OpenAPI / 前端 / MCP | Service 签名（`db, schedule_id, cancel_reason, operator_id`）不变；端点契约不变；`cancel_schedule` 不在 MCP Tool 集合 |
| D7 | 不改 DB 结构 | `decrement_booked_count` 已用 `with_for_update` 按主键命中（已有主键索引）；无需新索引 / migration |
| D8 | 事务边界仍在 Service | `db.commit()` 仍在 Service 内（L314）；锁随 AsyncSession 在 commit 后释放；与 `_do_cancel_booking` 一致 |

## Dependency Analysis

- 复用：`MembershipCardService.restore_credit`（既有，含 `get_card_with_lock` + 幂等键查 DB txn）。
- 复用：`ScheduleRepository.decrement_booked_count`（既有，含 `with_for_update` 行锁）。
- 复用：`BookingRepository.search`（既有，含租户过滤）。
- 无新外部依赖；无 DB 结构变更；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响。
- 契约：`POST /schedules/{id}/cancel` 路径 / 方法 / 请求体（`ScheduleCancel`）/ 响应模型（dict，字段集合不变）不变 → 无需 `pnpm gen:types`。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 修复后正常取消流程仍能成功（无回归） | 低 | `test_cancel_schedule_normal_ok`（Service 直调）+ `test_http_cancel_schedule_normal_ok`（HTTP 端点）双重验证；正常路径下 for 循环无异常 → 直达 commit → 返回正确字段 |
| 修复前依赖"部分失败部分成功"语义的调用方（如有）受影响 | 低 | grep 已确认仅 router 一处调用；router 不读 `failed_bookings` / `failed_count`；返回 dict 字段集合不变 → 调用方零感知 |
| mock `restore_credit` 在 live_server 进程不生效 | 中 | HTTP 失败路径改用真实失败场景（构造 `used_credits=0` 的卡触发 `restore_credit` 真实抛 `HTTPException(400)`）；既端到端又精确 |
| 多 booking 测试触发 `uq_bookings_schedule_student_active` 唯一约束 | 中 | fixture 内通过 admin HTTP 创建 2 个临时 student（student_a / student_b），同一 schedule 下用不同 student 创建 booking，规避唯一约束 |
| 清理 card 时被 `MembershipCardTransaction` 外键引用阻塞 | 中 | `_cleanup` 增加按 card_id 清理 txn 的步骤；每步独立 session + commit，避免单步失败导致整个 session abort 阻塞后续清理 |
| 行锁在事务回滚后是否正确释放 | 低 | `decrement_booked_count` 的 `with_for_update` 行锁生命周期由 AsyncSession 管理；raise 后 session 不 commit → with 退出 / FastAPI 依赖清理时 rollback → 锁随 session 释放 |
| 幂等键在事务回滚后是否影响重试 | 低 | `restore_credit` 内 `db.add(txn)` + `await db.flush()` 将 txn 写入 session；事务回滚时 INSERT 的 txn 也回滚 → 幂等键查询回到初始状态 → 下次重试不会因幂等短路而漏回补 |

## Implementation Steps

1. `schedule/service.py` 重构 `cancel_schedule` → py_compile。
2. 编写 `test_cancel_schedule_rollback.py`，迭代至全绿。
3. 静态审查 diff（仅允许 service.py + 新测试文件）。
4. 回归：`test_checkin_complete_lock.py` + `test_booking_ownership.py` + `test_auth_api.py`。

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1 | `test_cancel_schedule_normal_ok`（Service 直调）+ `test_http_cancel_schedule_normal_ok`（HTTP） |
| AC-2 | `test_cancel_schedule_restore_credit_failure_rolls_back_all`（monkeypatch）+ `test_http_cancel_schedule_restore_failure_rolls_back`（真实失败） |
| AC-3 | `test_cancel_schedule_partial_failure_rolls_back_prior_success`（mock 第 2 次失败） |
| AC-4 | `test_cancel_schedule_no_bookings_ok` |
| AC-5 | `test_cancel_schedule_already_cancelled_fails` + `test_http_cancel_schedule_already_cancelled_fails` |
| AC-6 | `test_http_cancel_schedule_normal_ok` |
| AC-7 | `test_http_cancel_schedule_restore_failure_rolls_back` |
| AC-8 | 回归 `test_checkin_complete_lock.py` + `test_booking_ownership.py` + `test_auth_api.py` |
| AC-9 | 静态 grep：Service 调 `repo.decrement_booked_count` 与 `booking_repo.search`；无裸 `with_for_update` / `db.execute` 直写；`db.commit()` 在 Service；跨模块仅调 `MembershipCardService.restore_credit` |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他仓库内脚本直接调 `ScheduleService.cancel_schedule` | grep 已确认仅 router 一处调用；MCP 无 `cancel_schedule` 工具；Service 签名不变 |
| U2 | `restore_credit` 内部 `get_card_with_lock` 用 `with_for_update`，事务回滚后行锁是否正确释放 | 行锁生命周期由 AsyncSession 管理；raise 后 session 不 commit → with 退出 / FastAPI 依赖清理时 rollback → 锁随 session 释放，无锁泄漏 |
| U3 | 多 booking 场景下，第一个 restore_credit 成功的 txn 在事务回滚后是否被回滚 | `restore_credit` 内 `db.add(txn)` + `await db.flush()` 将 txn 写入当前 session；事务回滚时所有 INSERT 都被回滚 → txn 不存在 → 幂等键查询回到初始状态，下次重试不会因幂等短路而漏回补 |
| U4 | HTTP 端点失败路径为何不用 monkeypatch | monkeypatch 仅替换测试进程的类属性，对 live_server 独立进程不生效；改用真实失败场景（构造 `used_credits=0` 的卡触发 `restore_credit` 真实抛 `HTTPException(400)` → 内层 except 包装为 `BusinessException(500)`），既端到端又精确 |
