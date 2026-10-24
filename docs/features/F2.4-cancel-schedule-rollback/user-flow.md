# F2.4 — cancel_schedule 回补失败回滚 · 用户流程

> 视角：管理员/教师（持 `schedule:cancel` 权限）通过 HTTP API 取消排期。
> 认证链路：所有端点要求 `Authorization: Bearer <token>` + `x-tenant-slug` 头。`current_user` 由 `Depends(get_current_user)` 注入；端点 `@require_permissions("schedule:cancel")` 校验权限通过。

---

## 流程 1：正常取消排期（POST /api/v1/schedules/{schedule_id}/cancel）

**主流程（含 BOOKED 预约 + 关联会员卡）**

1. 管理员/教师调 `POST /schedules/{schedule_id}/cancel`，请求体 `{ "cancel_reason": "老师临时调课" }`。
2. Router：`get_current_user` 注入身份；`@require_permissions("schedule:cancel")` 校验通过；调 `schedule_service.cancel_schedule(db, schedule_id, cancel_reason=data.cancel_reason, operator_id=current_user.user_id)`。
3. Service `cancel_schedule`：
   - `schedule = await self.repo.get_by_id(db, schedule_id)`（含租户过滤；跨租户 / 不存在 → None → 404）。
   - status 校验：`CANCELLED` → 400"排期已取消"；`FINISHED` → 400"排期已完成，无法取消"。
   - `bookings, _ = await booking_repo.search(db, schedule_id=..., status=BOOKED, page=1, page_size=1000)`（含租户过滤）。
   - for booking in bookings：
     - `booking.status = CANCELLED`；`booking.cancelled_at = now(UTC)`；`booking.cancelled_reason = f"老师取消课程: {cancel_reason}"`。
     - `await self.repo.decrement_booked_count(db, schedule_id)`（`SELECT ... FOR UPDATE` 行锁 + `booked_count -= 1`，含 Check 约束 `booked_count >= 0`）。
     - 若 `booking.membership_card_id`：
       - `idempotency_key = f"schedule_cancel_{booking.id}_{schedule_id}"`。
       - `try: await membership_card_service.restore_credit(db, card_id=..., tenant_id=..., booking_id=..., idempotency_key=...)`。
       - `except Exception as e: logger.error(...); raise BusinessException(f"会员卡恢复次数失败，取消排期操作已撤销: {e}", code=500)`。
   - `update_data = {"status": CANCELLED, "cancel_reason": ..., "cancelled_by": operator_id, "cancelled_at": now}`；`schedule = await self.repo.update(db, schedule_id, update_data)`。
   - `await db.commit()`（锁随 session 释放）；`await db.refresh(schedule)`。
   - 返回 `{schedule_id, total_bookings, success_count: total_bookings, failed_count: 0, failed_bookings: []}`。
4. Router 构造 msg：`total_bookings > 0` → `f"排期已取消，已处理 {success_count}/{total_bookings} 个学员预约"`；否则 `"排期已取消"`。返回 `{code:0, msg, data: result}`。

**异常流程**

- 未认证 → 401；无 `schedule:cancel` 权限 → 403；缺租户头 → 400。
- schedule 不存在 / 跨租户 → 404"排期不存在"。
- 已 CANCELLED → 400"排期已取消"。
- 已 FINISHED → 400"排期已完成，无法取消"。

## 流程 2：restore_credit 失败 → 整体回滚（核心修复场景）

**修复前（外层吞异常，脏提交，BUG）**

1. schedule=10 含 2 个 BOOKED booking（A, B），各关联卡（card 100/200，各 used_credits=1）。
2. cancel_schedule(10)：
   - loop A：booking A.status=CANCELLED；decrement → booked_count=1；restore_credit(card 100) → SUCCESS（事务内 INSERT txn，card 100.used_credits=0）。
   - loop B：booking B.status=CANCELLED；decrement → booked_count=0；restore_credit(card 200) → FAILURE。
   - **外层 except 接住异常** → `failed_bookings.append({2, ...})`；循环结束。
   - update schedule.status=CANCELLED；`db.commit()` ← **提交了 A 的全部 + B 的部分 + schedule 变更**。
3. 结果：schedule=CANCELLED, booked_count=0, booking A=CANCELLED, booking B=CANCELLED, card 100.used_credits=0, card 200.used_credits=1（**未恢复，脏数据**）。学员 B 的卡被"白扣 1 次"。

**修复后（异常传播，整体回滚）**

1. schedule=10 含 2 个 BOOKED booking（A, B），各关联卡。
2. cancel_schedule(10)：
   - loop A：booking A.status=CANCELLED；decrement → booked_count=1；restore_credit(card 100) → SUCCESS（事务内 INSERT txn，card 100.used_credits=0）。
   - loop B：booking B.status=CANCELLED；decrement → booked_count=0；restore_credit(card 200) → FAILURE。
   - **内层 except 捕获** → `raise BusinessException(500, "会员卡恢复次数失败，取消排期操作已撤销: ...")`。
   - **异常直接传播出 `cancel_schedule`** → `db.commit()` 永不执行。
   - AsyncSession 被 `with` 退出 / FastAPI 依赖清理 → **ROLLBACK** → A 的所有变更（status/decrement/INSERT txn/card.used_credits）+ B 的所有变更（status/decrement）+ schedule 变更全部回滚。
3. 全局异常处理器捕获 `BusinessException(500)` → 返回统一信封 `{code:500, msg:"会员卡恢复次数失败，取消排期操作已撤销: ...", data:null}`（无 Traceback，不回显内部异常类型）。
4. 结果：schedule=NORMAL, booked_count=2, booking A=BOOKED, booking B=BOOKED, card 100.used_credits=1, card 200.used_credits=1。**一切回到初始状态**，运营可重试取消或排查 card 200 异常原因。

## 流程 3：单 booking restore_credit 失败 → 整体回滚

修复后：
1. schedule=10 含 1 个 BOOKED booking（关联 card 100，used_credits=1）。
2. cancel_schedule(10)：loop：booking.status=CANCELLED；decrement → booked_count=0；restore_credit(card 100) → FAILURE（如 card 100.used_credits=0 → restore_credit 内部 `if used_credits <= 0: raise HTTPException(400)` → 被内层 except 包装为 `BusinessException(500)`）。
3. raise 传播出方法 → `db.commit()` 永不执行 → AsyncSession ROLLBACK。
4. 全局异常处理器返回 500 信封。
5. 结果：schedule=NORMAL, booked_count=1, booking=BOOKED, card.used_credits=0（原本就是 0，未变）。学员可联系运营检查 card 状态。

## 流程 4：schedule 无 BOOKED 预约 → 直接成功

1. schedule=10，无 BOOKED 预约（booked_count=0）。
2. cancel_schedule(10)：`bookings, _ = await booking_repo.search(...)` → `bookings == []`。
3. for 循环不执行；直接 update schedule.status=CANCELLED；`db.commit()`；返回 `{total_bookings:0, success_count:0, ...}`。
4. 结果：schedule=CANCELLED, booked_count=0。

## 流程 5：状态校验失败（单请求）

- 已 CANCELLED 排期再取消：`get_by_id` 后 status==CANCELLED → 400"排期已取消"。
- 已 FINISHED 排期取消：status==FINISHED → 400"排期已完成，无法取消"。
- 不存在的 schedule_id / 跨租户：`get_by_id` 含租户过滤 → None → 404"排期不存在"（不泄露存在性）。

## 流程 6：跨模块调用链

```
HTTP POST /schedules/{id}/cancel
  → schedule.router.cancel_schedule
    → schedule.service.cancel_schedule (事务边界在此)
      → schedule.repo.get_by_id            (读 schedule, 含租户过滤)
      → booking.repo.search               (读 BOOKED bookings, 含租户过滤)
      → schedule.repo.decrement_booked_count  (FOR UPDATE 行锁 + UPDATE)
      → membership.service.restore_credit    (跨模块 Service 调用, 内含 get_card_with_lock + INSERT txn)
      → schedule.repo.update               (UPDATE schedule 状态)
      → db.commit()                        (一次性提交, 锁释放)
    → 返回 dict
  → router 构造 msg + success 信封
```

不直接调 `BookingRepository`、不裸 SQL、不在 schedule Service 内重新实现扣次/恢复逻辑，跨模块仅通过 `MembershipCardService` 入口调用。
