# F2.1 — admin 用户管理真实化 · 用户流程

> 视角：机构管理员（admin / super_admin）通过 HTTP API 操作用户管理。
> 认证链路：所有端点（除 `/admin/public/stats`）要求 `Authorization: Bearer <token>` + `x-tenant-slug` 头；`/admin/public/stats` 无认证但按租户中间件现状需携带租户头（否则 400）。

---

## 流程 1：创建用户（POST /api/v1/admin/users）

**主流程**

1. 管理员提交 `{username, phone, password, email?, is_active?, role_ids?}`。
2. Router：Pydantic 校验（手机号正则、密码长度）→ `@require_permissions("user:create")`。
3. `AdminUserService.create_user` 将 admin 契约映射为 `user.schemas.UserCreate`（`username → nickname`）。
4. `UserService.create_user`：
   - 校验手机号唯一（本租户内）→ 邮箱唯一；
   - 创建 User（密码哈希、tenant_id 由 `TenantAwareRepository` 注入）；
   - 按 `role_ids` 分配角色；若含 teacher/student 角色代码则自动创建对应 Profile；
   - 提交事务。
5. 返回 201 + 真实用户数据（含 `id`、`public_id`、`roles`、`username`/`is_active` 兼容别名）。

**异常流程**

- 手机号已存在 → `ValidationException("手机号已被注册")` → 400，无落库。
- 邮箱已被使用 → 400，无落库。
- 无 `user:create` 权限（如 student）→ 403。
- 未认证 → 401；缺租户头 → 400。

## 流程 2：用户列表（GET /api/v1/admin/users?page=&page_size=&keyword=）

**主流程**

1. `@require_permissions("user:read")` 通过。
2. `AdminUserService.list_users` → `UserService.list_users` → `UserRepository.search`（自动租户过滤 + 软删除过滤 + 关键词匹配手机号/昵称/姓名）。
3. 返回 `{total, page, page_size, items}`，items 为真实用户（含角色代码、兼容别名）。

**异常流程**

- 无权限 → 403。keyword 无匹配 → `total=0, items=[]`（正常空态）。

## 流程 3：用户详情（GET /api/v1/admin/users/{user_id}）

1. `@require_permissions("user:read")` → `AdminUserService.get_user` → `UserService.get_user_by_id`。
2. 存在 → 200 真实数据；不存在 / 已删除 / 跨租户 → `NotFoundException` → 404。

## 流程 4：更新用户（PUT /api/v1/admin/users/{user_id}）

**主流程**

1. `@require_permissions("user:update", "user:read", require_all=True)`。
2. Router 以 `exclude_unset=True` 提取部分更新字段。
3. `AdminUserService.update_user` 映射（`username → nickname`、`is_active → status`）→ `UserService.update_user`：
   - 用户存在性校验（租户隔离）；手机号/邮箱变更唯一性校验；
   - 状态变更联动 TeacherProfile/StudentProfile 状态；
   - 若传 `role_ids` → 内部调用 `assign_roles`（覆盖式）并清权限缓存；
   - 提交事务。
4. 返回更新后的真实用户数据。

**异常流程**

- 用户不存在 → 404。手机号/邮箱冲突 → 400。部分更新为空 → 返回原数据（幂等）。

## 流程 5：删除用户（DELETE /api/v1/admin/users/{user_id}）

**主流程**

1. `@require_permissions("user:delete")`。
2. `AdminUserService.delete_user` 先做"不能删除自己"预检 → `UserService.delete_user`：
   - 再次校验不能删除自己（纵深防御）；
   - 教师有未来未完成排课 → 拒绝；
   - 软删除（`deleted_at` 置位）；清除该用户权限缓存；提交。
3. 返回 `{"message": "用户 {id} 已删除"}`。

**异常流程**

- 删除自己 → 400 `不能删除自己的账号`。
- 教师有未来排课 → 400，提示先取消排课。
- 用户不存在 → 404。

## 流程 6：分配角色（POST /api/v1/admin/users/{user_id}/assign-roles?role_ids=）

**主流程**

1. 双重校验：`@require_roles("admin", "manager")` + `@require_permissions("role:assign")`。
2. `AdminUserService.assign_roles` → `UserService.assign_roles`：
   - 操作人必须为 admin / super_admin（Service 层再校验，manager 角色在此被拒绝 —— 纵深防御）；
   - 覆盖式删除旧角色、写入新角色；
   - 联动 TeacherProfile（创建/激活/停用）与 StudentProfile（创建/删除）；
   - 提交事务；清除目标用户权限缓存。
3. 返回 `{"user_id", "role_ids"}`。

**异常流程**

- 目标用户不存在 → 404。操作人非管理员 → 403（PermissionException）。角色 ID 不存在 → 该 ID 被跳过（`get_role_by_id` 返回 None，不报错）。

## 流程 7：批量删除（POST /api/v1/admin/users/batch-delete?user_ids=）

**主流程（原子语义）**

1. `@require_roles("super_admin")`。
2. `AdminUserService.batch_delete_users`：
   - 预检：`user_ids` 不得包含操作者自己；
   - 循环调用 `UserService.delete_user(..., auto_commit=False)`（同一 `AsyncSession`，不逐条提交）；
   - 全部成功后 `db.commit()` 统一提交；统一清除所有被删用户权限缓存。
3. 返回 `{"deleted_count", "user_ids"}`。

**异常流程（全部回滚）**

- 包含操作者自己 / 任一用户不存在 / 任一教师有未来排课 → 抛业务异常，`get_session` 回滚 → 无任何用户被删除。

## 流程 8：公开统计（GET /api/v1/admin/public/stats）

1. 无需认证；按租户中间件现状需携带租户头（无头 → 400，与现状一致）。
2. `AdminUserService.get_public_stats` 以**当前租户**为范围真实聚合：
   - `total_students`：本租户拥有 student 角色的未删除用户数；
   - `total_teachers`：本租户拥有 teacher 角色的未删除用户数；
   - `total_classes`：本租户未删除课程数；
   - `total_bookings`：本租户预约总数。
3. 租户上下文缺失（理论上 HTTP 路径不可达）时降级为全平台聚合并在日志标注。
