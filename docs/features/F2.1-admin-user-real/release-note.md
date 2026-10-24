# F2.1 — Release Note

## admin 用户管理真实化（2026-09-27）

### 功能变更

- `POST /api/v1/admin/users`：真实创建用户（手机号/邮箱唯一性校验、角色分配、teacher/student 自动建档、密码哈希）。
- `GET /api/v1/admin/users`：真实分页列表（租户隔离、软删过滤、关键词搜索）。
- `GET /api/v1/admin/users/{id}`：真实详情（不存在/已删除 → 404）。
- `PUT /api/v1/admin/users/{id}`：真实部分更新；`is_active=false` 停用账号；传 `role_ids` 覆盖角色并即时失效权限缓存。
- `DELETE /api/v1/admin/users/{id}`：真实软删除；不能删除自己（400）；教师有未来排课拒绝删除。
- `POST /api/v1/admin/users/{id}/assign-roles`：真实覆盖式角色分配，权限缓存即时失效。
- `POST /api/v1/admin/users/batch-delete`：真实批量软删除，**原子语义** —— 任一用户校验失败（不存在/删自己/教师有排课）则整体回滚，不做部分删除。
- `GET /api/v1/admin/public/stats`：从硬编码改为按当前租户的真实聚合统计（学员数/教师数/课程数/预约数）。

### 兼容性

- API 路径、方法、请求体字段全部不变。
- 响应保留 `username`、`is_active` 字段（分别派生自 `nickname`、`status`），同时返回完整真实字段。
- 前端 4 端（admin-web / student-web / teacher-web / miniapp）当前无 `/admin/users*` 消费方，无影响；无需重新生成 api-types。

### 修复

- 修复 `AuthRepository.get_role_by_id` 缺失导致 `assign_roles` 调用必 500 的休眠缺陷。
- 修复 admin `PUT /users/{id}` 调用 Service 时缺少 `db` 实参的历史 bug。
- "不能删除自己"错误码由 500 修正为 400。

### 运维与数据

- 无数据库结构变更，无需迁移。
- 无配置/环境变量变更。

### 已知遗留（后续处理）

- `POST /api/v1/users`（无尾斜杠）405 的预先存在缺陷。
- `GET /admin/dashboard` SQL 位于 Router 层的历史分层债务。
- 角色 ID 跨租户引用缺乏校验（低危，操作受权限门禁）。
