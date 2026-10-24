# F2.4 — cancel_schedule 回补失败回滚 · 需求文档

> Feature ID：F2.4
> 作者：backend-engineer
> 日期：2026-09-28
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（纯后端任务，走 v2 轨道，不召前端；不触 DB 结构 → 不召 database-engineer 改库，仅复用既有 Repository 方法）
> 依赖：无（`MembershipCardService.restore_credit` 既有；`ScheduleRepository.decrement_booked_count` 既有）
> 前置 Feature：F2.3（签到/完成加行锁，已完成；共用 booking 模块的状态机校验模式）

---

## Goal

`ScheduleService.cancel_schedule` 取消排期时，逐个处理 BOOKED 预约并恢复课时。当前实现用外层 `try/except` 吞掉异常 → 失败的 booking 被追加到 `failed_bookings` 列表但循环继续 → 末尾 `db.commit()` 提交了"部分成功"的脏状态（status 已改 CANCELLED、booked_count 已减、但 credit 未恢复）→ 数据不一致。

修复目标：移除外层 `try/except`，任一 booking 处理失败（含 `restore_credit` 失败）都直接 raise → `db.commit()` 永不执行 → AsyncSession 被动回滚 → 全部变更不落地，保证数据一致。与既有 `BookingService._do_cancel_booking` 同构。

## User Story

作为管理员/教师（`schedule:cancel` 权限），
我希望取消排期时如果某学员的课时回补失败，整个取消操作被撤销，以便：

- 不会出现"schedule 已 CANCELLED 但 booking 仍 BOOKED、booked_count 已减但 credit 未恢复"的脏数据。
- 不会出现"部分 booking 已 CANCELLED、部分仍 BOOKED"的中间状态——取消是原子事务，要么全部成功要么全部回滚。
- 学员能在恢复失败后再次看到完整的原始排期与预约，自行重试取消或联系运营。

作为系统，
我希望 `cancel_schedule` 的事务模型与 `_do_cancel_booking`（单 booking 取消，restore 失败已 raise + 回滚）保持同构，以便事务边界统一、可审计、可维护。

## Background / 现状（已核查的代码事实）

| 事实 | 证据 |
|------|------|
| `cancel_schedule` 外层 try/except 吞异常 | [service.py:272-299](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L272-299)（修复前）：`for booking in booking_list: try: ... except Exception as e: failed_bookings.append(...)` —— 异常被吞 → 循环继续 |
| 失败 booking 部分状态被提交 | [service.py:308](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L308)（修复前）：`await db.commit()` 在循环后无条件执行 → 已变更的 `booking.status=CANCELLED` / `booked_count-=1` 被提交，但 `restore_credit` 未执行 → 脏数据 |
| 内层 try/except 已 raise，被外层吞掉 | [service.py:283-293](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L283-293)（修复前）：`try: await restore_credit(...) except Exception as e: logger.error(...); raise` —— raise 出去后被外层 except 接住 |
| `_do_cancel_booking` 已是正确模式 | [booking/service.py:198-272](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L198-272)：restore_credit 失败 → `raise BusinessException(f"会员卡恢复次数失败，取消预约操作已撤销: {e}", code=500)` → 不 commit → session 回滚 |
| router 仅消费 `total_bookings` / `success_count` | [router.py:192-193](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/router.py#L192-193)：`if result["total_bookings"] > 0: msg = f"...{result['success_count']}/{result['total_bookings']}..."` —— 不读 `failed_bookings` / `failed_count` |
| `MembershipCardService.restore_credit` 自带幂等键 | [membership/service.py:1399-1443](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1399-1443)：`idempotency_key` 查 DB 中的 `MembershipCardTransaction`；事务回滚后 INSERT 的 txn 也回滚 → 幂等键回到初始状态，下次重试不会因幂等短路而漏回补 |
| `ScheduleRepository.decrement_booked_count` 已含 FOR UPDATE | [repository.py:197-220](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/repository.py#L197-220)：`select(CourseSchedule).where(...).with_for_update()` → 排期行锁，防止并发取消竞态 |
| `BookingRepository.search` 返回 `(list, total)` | [booking/repository.py:22-98](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L22-98)：签名 `-> tuple[list[Booking], int]` —— 修复前用 `bookings[0]` 取 list，本次顺手改为 `bookings, _ = ...` 解构更清晰 |

## 数据不一致场景示意（修复前 vs 修复后）

**修复前（外层吞异常，脏提交）**

```
schedule=10, booked_count=2, status=NORMAL
  booking A (id=1, card=100, used_credits=1)  BOOKED
  booking B (id=2, card=200, used_credits=1)  BOOKED

cancel_schedule(10):
  loop A: booking.status=CANCELLED; decrement → booked_count=1;
          restore_credit(card=100) → SUCCESS（card.used_credits=0）
          success_count=1
  loop B: booking.status=CANCELLED; decrement → booked_count=0;
          restore_credit(card=200) → FAILURE（HTTPException 400）
          → except 接住 → failed_bookings.append({2, ...})
          success_count 不变
  update schedule.status=CANCELLED, cancelled_at=now
  db.commit()  ← 提交了 A 的全部变更 + B 的部分变更（status/booked_count 已改）+ schedule 变更

结果：schedule=CANCELLED, booked_count=0, booking A=CANCELLED, booking B=CANCELLED
      card 100.used_credits=0（恢复成功）, card 200.used_credits=1（未恢复！）
      ← 学员 B 的卡被"白扣 1 次"，运营难追溯
```

**修复后（异常传播，整体回滚）**

```
schedule=10, booked_count=2, status=NORMAL
  booking A (id=1, card=100)  BOOKED
  booking B (id=2, card=200)  BOOKED

cancel_schedule(10):
  loop A: booking.status=CANCELLED; decrement → booked_count=1;
          restore_credit(card=100) → SUCCESS（事务内 INSERT txn）
  loop B: booking.status=CANCELLED; decrement → booked_count=0;
          restore_credit(card=200) → FAILURE
          → except 捕获 → raise BusinessException(500, "会员卡恢复次数失败，取消排期操作已撤销: ...")
  db.commit() ← 永不执行（异常已传播出方法）
  AsyncSession 被 with / FastAPI 依赖清理 → ROLLBACK

结果：schedule=NORMAL, booked_count=2, booking A=BOOKED, booking B=BOOKED
      card 100.used_credits=1（恢复的 txn 被回滚）, card 200.used_credits=1
      ← 一切回到初始状态，学员可重试
```

## Scope（In Scope）

1. `schedule/service.py`：
   - 移除 `cancel_schedule` 的外层 `try/except`（修复前 L272-299）：异常直接传播。
   - 内层 `try/except` 改为 `raise BusinessException(f"会员卡恢复次数失败，取消排期操作已撤销: {e}", code=500)`（与 `_do_cancel_booking` 同构）。
   - 移除 `success_count` / `failed_bookings` 累加（事务回滚后这些计数无意义）；保留返回 dict 字段集合以维持 router 兼容（正常路径下 `success_count == total_bookings`，`failed_count == 0`，`failed_bookings == []`）。
   - 顺手把 `bookings = await ...; booking_list = bookings[0]` 改为 `bookings, _ = await ...` 解构（语义更清晰，零行为变更）。
   - 补 docstring 明确事务边界模型。
2. 新增集成测试 `apps/api/tests/integration/test_cancel_schedule_rollback.py`：
   - 正常取消（含 booking+card）→ 全部 CANCELLED + credit 恢复 + schedule CANCELLED。
   - mock restore_credit 抛异常 → cancel_schedule raise BusinessException(500) → 整体回滚。
   - 多 booking 场景，中途 restore_credit 失败 → 已处理成功的 booking 变更也回滚。
   - 无 BOOKED 预约 → cancel_schedule 直接成功。
   - 已 CANCELLED / FINISHED 排期再取消 → 400。
   - 不存在 schedule → 404。
   - HTTP 端点正常路径 → 200 + 信封字段正确。
   - HTTP 端点失败路径（构造 used_credits=0 真实失败）→ 500 + 信封 + 无 Traceback + DB 回滚。
   - 学员无 `schedule:cancel` 权限 → 403。

## Out of Scope

- 不修改 `schedule/router.py`（Service 签名不变，端点装饰器不变；router 仅消费 `total_bookings` / `success_count`，仍兼容）。
- 不修改 `schedule/repository.py`（`decrement_booked_count` 已含 FOR UPDATE）。
- 不修改 `membership/service.py`（`restore_credit` 既有；幂等键查 DB txn，事务回滚后自动回到初始状态）。
- 不修改 `booking/service.py` / `booking/repository.py`（`_do_cancel_booking` 已是正确模式，本 Feature 仅让 `cancel_schedule` 与之同构）。
- 不修改 OpenAPI 契约（路径 / 方法 / 请求体 / 响应模型不变；返回 dict 字段集合不变）。
- 不修改前端 4 端（admin-web / student-web / teacher-web / miniapp）。
- 不修改 MCP（`cancel_schedule` 不在 MCP Tool 集合内，AI 侧通过 `cancel_booking` Tool 取消单预约）。
- 不修改 DB 结构、不新增索引、不写 migration。
- 不引入新依赖。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1：正常取消（含 booking+card）→ schedule CANCELLED、booking CANCELLED、`cancelled_at` 非空、`booked_count=0`、`card.used_credits` 恢复 1→0。
- AC-2：mock `restore_credit` 抛异常 → `cancel_schedule` raise `BusinessException(code=500)` 且 msg 含"会员卡恢复次数失败"与"取消排期操作已撤销"；DB 无任何变更（schedule 仍 NORMAL、`booked_count` 不变、booking 仍 BOOKED、`cancelled_at` 仍 None、`card.used_credits` 不变）。
- AC-3：多 booking 场景，第一个 restore 成功、第二个失败 → 整体回滚 → 第一个的变更（status/decrement/credit 恢复）也回滚。
- AC-4：schedule 无 BOOKED 预约 → `cancel_schedule` 直接成功，`total_bookings=0`。
- AC-5：已 CANCELLED 排期再取消 → 400"排期已取消"。
- AC-6：HTTP `POST /schedules/{id}/cancel` 正常路径 → 200 + 信封字段正确 + 无 Traceback。
- AC-7：HTTP 失败路径 → 500 + 信封 + msg 含"会员卡恢复次数失败" + 无 Traceback + DB 整体回滚。
- AC-8：回归 `test_checkin_complete_lock.py` + `test_booking_ownership.py` + `test_auth_api.py` 全量通过。
- AC-9：分层合规——Service 走 Repository 的 `decrement_booked_count` 与 `BookingRepository.search`；事务边界在 Service（`db.commit()` 仍在 Service 内）；跨模块调用走 `MembershipCardService.restore_credit`，不裸 SQL。

## Dependencies

- 复用：`MembershipCardService.restore_credit`（既有，含幂等键 + `get_card_with_lock`）。
- 复用：`ScheduleRepository.decrement_booked_count`（既有，含 FOR UPDATE 行锁）。
- 复用：`BookingRepository.search`（既有，含租户过滤）。
- 无新外部依赖；无 DB 结构变更；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响。

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他调用方直接调 `ScheduleService.cancel_schedule`（不经 router） | grep 已确认仅 router 一处调用；MCP 无 `cancel_schedule` 工具（AI 侧通过 `cancel_booking` 取消单预约）。Service 签名不变，即便有遗漏调用方也不受影响 |
| U2 | `MembershipCardService.restore_credit` 内部 `get_card_with_lock` 用 `with_for_update`，事务回滚后行锁是否正确释放 | 行锁生命周期由 AsyncSession 管理；raise 后 session 不 commit → with 退出 / FastAPI 依赖清理时 rollback → 锁随 session 释放，无锁泄漏 |
| U3 | 多 booking 场景下，第一个 restore_credit 成功的 txn 在事务回滚后是否被回滚 | `restore_credit` 内 `db.add(txn)` + `await db.flush()` 将 txn 写入当前 session；事务回滚时所有 INSERT 都被回滚 → txn 不存在 → 幂等键查询回到初始状态，下次重试不会因幂等短路而漏回补 |
| U4 | HTTP 端点失败路径为何不用 monkeypatch | monkeypatch 仅替换测试进程的类属性，对 live_server 独立进程不生效。改用真实失败场景（构造 `used_credits=0` 的卡触发 `restore_credit` 真实抛 `HTTPException(400)` → 内层 except 包装为 `BusinessException(500)`），既端到端又精确 |
