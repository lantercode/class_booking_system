# F1.1 — RBAC 权限校验真实生效 · 验收标准

> Feature ID：F1.1
> 日期：2026-09-27
> 关联文档：[requirement.md](./requirement.md) / [runtime-test-report.md](./runtime-test-report.md)

---

## AC-1 配置与开关

| 编号 | 验收项 | 验证方式 |
|------|--------|---------|
| AC-1.1 | `core/config.py` Settings 含 `PERMISSION_CHECK_BYPASS: bool = False` | 读代码 |
| AC-1.2 | `checker.py` 无硬编码 bypass 常量；4 处校验函数均通过 `get_settings().PERMISSION_CHECK_BYPASS` 实时读取 | 读代码 + grep |
| AC-1.3 | `.env` 与 `.env.example` 含 `PERMISSION_CHECK_BYPASS=false` | 读文件 |
| AC-1.4 | 默认配置下（未设置环境变量）权限校验真实执行 | AC-2.x 集成测试 |

## AC-2 权限强制执行（对应 Feature AC：无权限用户访问受保护接口返回 403）

| 编号 | 验收项 | 期望 |
|------|--------|------|
| AC-2.1 | 学员 `POST /api/v1/users/`（合法请求体） | 403 |
| AC-2.2 | 学员 `GET /api/v1/admin/users` | 403 |
| AC-2.3 | super_admin `DELETE /api/v1/courses/{id}` | 非 401/403（权限放行，业务结果不限） |
| AC-2.4 | 无 token `GET /api/v1/users` | 401 |

## AC-3 学员访问 /admin/* 返回 403（Feature AC 直接项）

| 编号 | 验收项 | 期望 |
|------|--------|------|
| AC-3.1 | 学员 `GET /api/v1/admin/users` | 403（同 AC-2.2） |
| AC-3.2 | 学员 `GET /api/v1/admin/settings` | 403 |

## AC-4 写操作端点 RBAC 装饰器（Feature AC：所有写操作端点有 RBAC 装饰器）

| 编号 | 端点 | 装饰器 | 验证 |
|------|------|--------|------|
| AC-4.1 | `POST /bookings/` | `require_roles("student")` | 学员非 403 / 教师 403 |
| AC-4.2 | `POST /bookings/{id}/cancel`、`POST /bookings/cancel` | `require_roles("student")` | 代码审查 |
| AC-4.3 | `POST /membership/cards/activate`、`POST /membership/cards/student-unfreeze` | `require_roles("student")` | 代码审查 |
| AC-4.4 | `PATCH /auth/me` | `require_roles(四角色)` | 代码审查 |
| AC-4.5 | `POST /common/upload` | `require_roles(四角色)` | 代码审查 |
| AC-4.6 | `GET /teachers/me`、`PATCH /teachers/me` | `require_roles("teacher")` | 学员访问 403（AC-4.8） |
| AC-4.7 | `GET /tenant/settings` | `require_roles("admin","super_admin")` | 学员 403 / admin 非 403 |
| AC-4.8 | 学员 `GET /api/v1/teachers/me` | — | 403 |
| AC-4.9 | 教师 `POST /api/v1/bookings/` | — | 403 |
| AC-4.10 | admin `GET /api/v1/admin/settings` | — | 200 |
| AC-4.11 | admin `GET /api/v1/tenant/settings` | — | 非 401/403 |

## AC-5 调试端点清理

| 编号 | 验收项 | 期望 |
|------|--------|------|
| AC-5.1 | `GET /api/v1/common/test-token` | 404 |
| AC-5.2 | `GET /api/v1/common/test-exception` | 404 |
| AC-5.3 | `GET /api/v1/common/test-auth` | 404 |
| AC-5.4 | `GET /api/v1/common/health` | 200（保持公开） |
| AC-5.5 | `common/router.py` 不再 import `create_access_token` 及未使用的异常类 | 读代码 |

## AC-6 AI 端点认证

| 编号 | 验收项 | 期望 |
|------|--------|------|
| AC-6.1 | 无 token `GET /api/v1/ai/intents` | 401 |
| AC-6.2 | 有 token `GET /api/v1/ai/intents` | 非 401（端点功能 bug D-F1.1-1 不在本 Feature 范围） |

## AC-7 种子数据与装饰器修复

| 编号 | 验收项 | 验证方式 |
|------|--------|---------|
| AC-7.1 | `scripts/seed.py` 与 `tests/conftest.py` 权限列表均含 `admin:all`、`super:manage` | 读代码 |
| AC-7.2 | 两处 admin 角色权限集均含 7 个新权限 | 读代码 + diff 一致性 |
| AC-7.3 | `admin/router.py` `batch_delete_users` 为 `@require_roles("super_admin")` | 读代码 |
| AC-7.4 | `admin/router.py` `GET /admin/settings` 为 `@require_roles("admin","super_admin")` 且签名含 `db` | 读代码 + AC-4.10 |

## AC-8 回归

| 编号 | 验收项 | 期望 |
|------|--------|------|
| AC-8.1 | `tests/integration/test_auth_api.py` | 25/25 通过（单独运行） |
| AC-8.2 | `tests/integration/test_rbac_real_redis.py` | 7/7 通过 |
| AC-8.3 | `tests/test_agent_runtime.py` | 5/5 通过 |
| AC-8.4 | 所有改动文件 `py_compile` 通过 | 14/14 |
| AC-8.5 | 已知预存失败（test_tenant_isolation 3 个 / test_mcp_server 4 个）不扩大 | 记录不修 |

## AC-9 范围控制

| 编号 | 验收项 | 期望 |
|------|--------|------|
| AC-9.1 | 不修改 Service 层业务逻辑 | git diff 审查 |
| AC-9.2 | 不修改 `packages/api-types`、无 OpenAPI 契约变更 | git diff 审查 |
| AC-9.3 | 前端四端零改动 | git diff 审查 |
| AC-9.4 | 不新增权限模型 / 不重构 RBAC 架构 | git diff 审查 |
