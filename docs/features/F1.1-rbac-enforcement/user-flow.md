# F1.1 — RBAC 权限校验真实生效 · 用户流程

> Feature ID：F1.1
> 日期：2026-09-27
> 关联文档：[requirement.md](./requirement.md) / [acceptance.md](./acceptance.md)

---

## 1. 正常流程（权限校验通过）

### 1.1 管理员执行管理操作

1. admin 登录，获得 JWT（`POST /api/v1/auth/login`）。
2. 携带 `Authorization: Bearer <token>` + `x-tenant-slug` 头请求管理端点，如 `DELETE /api/v1/courses/{id}`。
3. `get_current_user` 校验 token（含黑名单检查），注入 `user_id`/`tenant_id`。
4. `@require_permissions("course:delete")` 装饰器执行：checker 查 Redis 缓存（miss 则查 DB 并回填），admin 角色拥有该权限 → 放行。
5. Service 层执行业务逻辑，返回正常响应。

### 1.2 学员执行学员操作

1. student 登录。
2. 请求 `POST /api/v1/bookings/`（创建预约）。
3. `@require_roles("student")` 校验通过 → 进入业务层（后续容量/冲突等业务校验不变）。

### 1.3 教师访问教师端点

1. teacher 登录。
2. 请求 `GET /api/v1/teachers/me`。
3. `@require_roles("teacher")` 校验通过 → 返回教师信息。

## 2. 越权流程（403）

### 2.1 学员访问管理端点

1. student 携带合法 token 请求 `GET /api/v1/admin/users`。
2. 认证通过（token 有效），进入 `@require_permissions("user:read")`。
3. checker 查询 student 角色权限集合，不含 `user:read` → 抛 `PermissionException`。
4. 统一异常体系返回 **HTTP 403**，信封 `{code: <业务码>, msg: "无权限执行该操作"}`。

### 2.2 教师创建预约（角色边界）

1. teacher 请求 `POST /api/v1/bookings/`。
2. `@require_roles("student")` 校验失败 → **403**。

### 2.3 学员访问教师/租户/管理配置端点

- `GET /api/v1/teachers/me` → 403（需 teacher 角色）
- `GET /api/v1/tenant/settings` → 403（需 admin/super_admin）
- `GET /api/v1/admin/settings` → 403（需 admin/super_admin）

## 3. 未认证流程（401）

1. 无 `Authorization` 头请求受保护端点（如 `GET /api/v1/users`、`GET /api/v1/ai/intents`）。
2. `get_current_user` 无法解析 token → 抛 `AuthException`。
3. 返回 **HTTP 401**（RBAC 装饰器在认证依赖之后执行，不会触达）。

## 4. 调试端点清理（404）

- `GET /api/v1/common/test-token`、`/test-exception`、`/test-auth` → 路由已删除，返回 **404**。
- `GET /api/v1/common/health` → 保持公开（在租户跳过白名单内），返回 200。

## 5. 权限变更生效流程（既有行为，未改动）

1. 管理员通过 `PUT /users/{id}/roles` 调整用户角色。
2. Service 层使该用户的 `perms:{tenant_id}:{user_id}` Redis 缓存失效。
3. 用户下一次请求时 checker 重新查库并回填缓存（最长 300s 延迟）。

---

## 异常矩阵汇总

| 场景 | HTTP 状态 | 触发点 |
|------|-----------|--------|
| 无 token / token 失效 / token 已登出 | 401 | `get_current_user` |
| 有 token 但角色/权限不足 | 403 | RBAC 装饰器 |
| 请求体验证失败 | 422 | FastAPI 内置（先于装饰器执行，不视为绕过） |
| 调试端点 | 404 | 路由不存在 |
| 租户头缺失（非白名单路径） | 400 | TenantASGIMiddleware（先于认证） |
