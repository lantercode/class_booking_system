# F2.2 — 预约数据归属与泄露修复 · 用户流程

> 视角：学员 / 教师 / 管理员通过 HTTP API 查询预约。
> 认证链路：所有端点要求 `Authorization: Bearer <token>` + `x-tenant-slug` 头。`current_user`（JWT payload）只含 `user_id` + `tenant_id`，角色由 Service 经 `app.core.rbac.checker.get_user_role_codes` 查 DB 取得。

---

## 流程 1：学员查自己的预约（GET /api/v1/bookings）

**主流程**

1. 学员 A 登录，携 token + 租户头。
2. Router：`get_current_user` 注入 `current_user={user_id, tenant_id}`；解析 `status`/`schedule_id`/`display_status` 等查询参数；**不在 Router 做角色判断**，直接 `current_user` 透传 Service。
3. `BookingService.list_bookings(db, current_user=current_user, ...)`：
   - 调 `get_user_role_codes(db, user_id, tenant_id)` → `{"student"}`；
   - 命中 student 分支 → `forced_student_id = user_id`（忽略任何外部 student_id 意图，本端点本就不暴露 student_id 查询参数）；
   - `BookingRepository.search(db, student_id=user_id, schedule_id=?, ...)` → 仅 A 自己的预约。
4. 返回 `{total, page, page_size, items}`，items 仅含 A 自己。

**异常流程**

- 未认证 → 401；缺租户头 → 400。

## 流程 2：学员尝试查他人预约（GET /api/v1/bookings/{booking_id}）

**主流程（拒绝）**

1. 学员 A 携带学员 B 的预约 ID 调 `GET /bookings/{B_id}`。
2. Router 透传 `current_user`。
3. Service `get_booking_by_id(db, B_id, current_user=current_user)`：
   - `repo.get_by_id(db, B_id)` 命中（同租户，租户隔离放行）；
   - `get_user_role_codes` → `{"student"}`，非 admin；
   - `booking.student_id (B) != user_id (A)` → 非 owner；
   - 学员无 teacher 角色 → 非 schedule 教师；
   - 抛 `PermissionException("无权查看该预约")` → 403。
4. 前端按统一信封 `{code:403, msg:"..."}` 处理。

**对照（查自己预约）**

- A 调 `GET /bookings/{A_id}` → `booking.student_id == user_id` → owner 放行 → 200。

## 流程 3：学员按 schedule_id 查（越权场景修复）

**修复前**：学员传 `schedule_id` → router 设 `student_id=None` → 返回该排期下全租户所有学员预约（泄露）。

**修复后**

1. 学员 A 调 `GET /bookings?schedule_id=<某排期>`。
2. Router 透传 `current_user`（不再因 schedule_id 把 student_id 置 None）。
3. Service student 分支强制 `student_id=user_id`，与 `schedule_id` 同时下推 Repository。
4. Repository `search(schedule_id=?, student_id=A, ...)` → 仅返回 A 在该排期的预约（通常 0 或 1 条）。

## 流程 4：教师查自己排期下的预约（GET /api/v1/bookings）

**主流程**

1. 教师 T 登录，调 `GET /bookings`。
2. Router 透传 `current_user`。
3. Service `list_bookings`：
   - `get_user_role_codes` → `{"teacher"}`（非 admin、非 student）；
   - 命中 teacher 分支 → `forced_teacher_id = user_id`；
   - `BookingRepository.search(db, teacher_id=T, ...)` → JOIN `CourseSchedule` WHERE `teacher_id=T` → T 名下排期的所有学员预约。
4. 返回 T 名下所有排期的预约列表。

**异常流程**

- 教师无任何排期 → 空列表（`total=0`）。
- 教师调 `GET /bookings?schedule_id=<非自己排期>` → teacher 分支强制 `teacher_id=T` 与 `schedule_id` 同时生效 → 该排期不属于 T → 空列表（不报错，最小泄露）。

## 流程 5：教师查/拒他人排期的预约详情（GET /api/v1/bookings/{id}）

**放行**

1. 教师 T 调 `GET /bookings/{其排期下预约 id}`。
2. Service：非 admin；`booking.student_id != T`（非 owner）；但 `"teacher" in roles` 且 `schedule.teacher_id == T` → 放行 200。

**拒绝**

1. 教师 T 调 `GET /bookings/{他人排期下预约 id}`。
2. Service：非 owner、非 admin；`schedule.teacher_id != T` → 403。

## 流程 6：管理员查全量（GET /api/v1/bookings 与 /bookings/{id}）

**主流程**

1. admin / super_admin 调 `GET /bookings` 或 `GET /bookings/{id}`。
2. Service：`get_user_role_codes` 命中 `{"admin"}` 或 `{"super_admin"}`（或并集）→ `is_admin=True` → 不加任何归属强制、不做 403 校验。
3. 全量返回（受 `schedule_id`/`status`/`display_status` 等既有过滤与租户隔离约束）。

## 流程 7：MCP `get_my_bookings` 工具（学员侧）

**主流程**

1. 学员通过 AI 对话触发 `get_my_bookings` 工具；AgentRuntime 从已认证上下文注入 `user_id` + `tenant_id`。
2. Tool：`_require_auth(user_id, tenant_id)`（Authentication + Tenant Validation）→ `set_tenant_id`。
3. `BookingService.list_bookings(db, current_user={"user_id":..., "tenant_id":...}, ...)`：
   - Service student 分支强制 `student_id=user_id`（与原行为一致）。
4. 返回学员自己的预约。

**教师侧（行为变更，符合 T2.2.3）**

- 教师通过 AI 触发 `get_my_bookings` → Service teacher 分支 → 返回其排期下的预约（而非空，原行为下教师非学员返回空）。
