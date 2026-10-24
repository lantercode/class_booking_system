# F2.3 — 签到/完成加行锁 · 用户流程

> 视角：管理员/教师（持 `booking:manage` 权限）通过 HTTP API 对预约执行签到/完成。
> 认证链路：所有端点要求 `Authorization: Bearer <token>` + `x-tenant-slug` 头。`current_user` 由 `Depends(get_current_user)` 注入（本 Feature 不消费 `current_user`，端点仅需 `booking:manage` 权限）。

---

## 流程 1：正常签到（POST /api/v1/bookings/{booking_id}/check-in）

**主流程（BOOKED → CHECKED_IN）**

1. 管理员/教师携 token + 租户头调 `POST /bookings/{booking_id}/check-in`。
2. Router：`get_current_user` 注入身份；`@require_permissions("booking:manage")` 校验权限通过；调 `booking_service.check_in_booking(db, booking_id)`。
3. Service `check_in_booking`：
   - `locked_booking = await self.repo.get_by_id_for_update(db, booking_id)`（SELECT ... FOR UPDATE，含租户过滤；跨租户 / 不存在 → None → 404）。
   - 拿到锁后读取 `locked_booking.status`：
     - `BOOKED` → 放行；
     - `CHECKED_IN` → 400「当前预约状态无法签到」；
     - 其余（`COMPLETED` / `CANCELLED` / `NO_SHOW`）→ 400「当前预约状态无法签到」。
   - `locked_booking.status = CHECKED_IN`；`locked_booking.checked_in_at = now(UTC)`。
   - `await db.commit()`（锁随 session 释放）；`await db.refresh(locked_booking)`。
4. 返回 `{code:0, msg:"签到成功", data: BookingResponse}`。

**异常流程**

- 未认证 → 401；无 `booking:manage` 权限 → 403；缺租户头 → 400。
- booking 不存在 / 跨租户 → 404「预约不存在」。
- status 非 `BOOKED` → 400「当前预约状态无法签到」。

## 流程 2：正常完成（POST /api/v1/bookings/{booking_id}/complete）

**主流程（BOOKED|CHECKED_IN → COMPLETED）**

1. 管理员/教师调 `POST /bookings/{booking_id}/complete`。
2. Router 透传到 `booking_service.complete_booking(db, booking_id)`。
3. Service `complete_booking`：
   - `locked_booking = await self.repo.get_by_id_for_update(db, booking_id)`。
   - 拿锁后重检 status：
     - `BOOKED` 或 `CHECKED_IN` → 放行；
     - `COMPLETED` → 400「当前预约状态无法完成」；
     - 其余（`CANCELLED` / `NO_SHOW`）→ 400「当前预约状态无法完成」。
   - `locked_booking.status = COMPLETED`。
   - `await db.commit()`；`await db.refresh(locked_booking)`。
4. 返回 `{code:0, msg:"课程已完成", data: BookingResponse}`。

**异常流程**

- status 既非 `BOOKED` 也非 `CHECKED_IN`（如 `COMPLETED`/`CANCELLED`/`NO_SHOW`）→ 400「当前预约状态无法完成」。

## 流程 3：并发签到（核心修复场景）

**修复前（无锁，BUG）**

1. 两个请求 T1 / T2 几乎同时到达 `POST /bookings/{10}/check-in`（booking 10 当前 `BOOKED`）。
2. T1 `get_by_id` → 读到 `BOOKED`；T2 `get_by_id` → 也读到 `BOOKED`（T1 未 commit，T2 不阻塞）。
3. T1 通过 status 检查 → 写 `CHECKED_IN` → commit。
4. T2 也通过 status 检查 → 写 `CHECKED_IN`（覆盖 `checked_in_at`）→ commit。
5. 结果：两次签到都"成功"（两个 200 响应），日志出现两条"签到成功"，`checked_in_at` 被后写入覆盖。

**修复后（FOR UPDATE 序列化）**

1. T1 / T2 同时到达。
2. T1 `get_by_id_for_update` → 拿到 booking 10 的行锁，读到 `BOOKED`。
3. T2 `get_by_id_for_update` → **阻塞等锁**（PG 行锁，不报错，等待 T1 释放）。
4. T1 通过检查 → 写 `CHECKED_IN` → commit → 释放锁。
5. T2 拿到锁，**重新读取** status = `CHECKED_IN` → 抛 `BusinessException("当前预约状态无法签到")` → rollback。
6. 结果：T1 返回 200，T2 返回 400「当前预约状态无法签到」。状态机一致。

## 流程 4：并发完成（核心修复场景）

**修复后**

1. booking 10 当前 `BOOKED`。T1 / T2 同时调 `POST /bookings/{10}/complete`。
2. T1 `get_by_id_for_update` → 拿锁，读 `BOOKED` → 写 `COMPLETED` → commit → 释放锁。
3. T2 等锁后拿到，重新读 `COMPLETED` → 抛 `BusinessException("当前预约状态无法完成")` → rollback。
4. 结果：一个 200，一个 400「当前预约状态无法完成」。

**变体（BOOKED → CHECKED_IN → COMPLETED → 再 complete）**

- 已 `COMPLETED` 再调 complete → 拿锁读 `COMPLETED` → 400「当前预约状态无法完成」（AC-6）。

## 流程 5：状态校验失败（单请求）

- 已 `CHECKED_IN` 再签到：拿锁读 `CHECKED_IN` → 400「当前预约状态无法签到」（AC-5）。
- `CANCELLED` 预约签到：拿锁读 `CANCELLED` → 400「当前预约状态无法签到」。
- `CANCELLED` 预约完成：拿锁读 `CANCELLED` → 400「当前预约状态无法完成」。

## 流程 6：跨租户 / 不存在

- 跨租户 booking_id：`get_by_id_for_update` 含 `tenant_id` 过滤 → None → 404「预约不存在」（不泄露存在性）。
- 不存在的 booking_id：None → 404。
