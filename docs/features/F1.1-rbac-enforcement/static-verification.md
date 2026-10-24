# F1.1 — RBAC 权限校验真实生效 · 静态验证报告

> Feature ID：F1.1
> 日期：2026-09-27

---

## 1. py_compile 验证（14/14 OK）

```text
OK src/app/core/rbac/checker.py
OK src/app/core/config.py
OK src/app/modules/common/router.py
OK src/app/modules/admin/router.py
OK src/app/modules/auth/router.py
OK src/app/modules/booking/router.py
OK src/app/modules/membership/router.py
OK src/app/modules/teacher/router.py
OK src/app/modules/tenant/router.py
OK src/app/modules/ai/router.py
OK src/app/ai/mcp_server.py
OK scripts/seed.py
OK tests/conftest.py
OK tests/integration/test_rbac_enforcement.py
```

## 2. 装饰器覆盖清单（grep 验证）

### 2.1 本次新增装饰器的端点

| 端点 | 装饰器 | 文件 |
|------|--------|------|
| PATCH /api/v1/auth/me | `@require_roles("student","teacher","admin","super_admin")` | auth/router.py |
| POST /api/v1/bookings/ | `@require_roles("student")` | booking/router.py |
| POST /api/v1/bookings/{id}/cancel | `@require_roles("student")` | booking/router.py |
| POST /api/v1/bookings/cancel | `@require_roles("student")` | booking/router.py |
| POST /api/v1/membership/cards/activate | `@require_roles("student")` | membership/router.py |
| POST /api/v1/membership/cards/student-unfreeze | `@require_roles("student")` | membership/router.py |
| GET /api/v1/teachers/me | `@require_roles("teacher")` | teacher/router.py |
| PATCH /api/v1/teachers/me | `@require_roles("teacher")` | teacher/router.py |
| GET /api/v1/tenant/settings | `@require_roles("admin","super_admin")` | tenant/router.py |
| GET /api/v1/ai/intents | `Depends(get_current_user)`（认证） | ai/router.py |
| POST /api/v1/common/upload | `@require_roles("admin","super_admin","teacher","student")` | common/router.py |
| GET /api/v1/admin/settings | `@require_roles("admin","super_admin")`（修改） | admin/router.py |
| POST /api/v1/admin/users/batch-delete | `@require_roles("super_admin")`（修改） | admin/router.py |

### 2.2 既有装饰器（未改动，抽验）

user/role/course/schedule/classroom/admin/membership 管理端点均已有 `@require_permissions`（如 `user:create`、`course:delete`、`role:assign` 等），本次未改动。

## 3. 危险符号清除验证

| 检查项 | 命令 | 结果 |
|--------|------|------|
| checker.py 无硬编码 bypass | grep `PERMISSION_CHECK_BYPASS = True` | 无匹配 |
| checker.py 4 处短路均走配置 | grep `_is_permission_check_bypass` | 5 处（定义 1 + 调用 4） |
| common/router.py 无 create_access_token | grep `create_access_token` | 无匹配 |
| 调试端点路由不存在 | grep `test-token\|test-exception\|test-auth` common/router.py | 无匹配 |
| config.py 新增配置 | grep `PERMISSION_CHECK_BYPASS` config.py | 1 处，默认 False |
| .env / .env.example | grep `PERMISSION_CHECK_BYPASS` | 各 1 处 `=false` |
| seed.py / conftest.py 权限一致 | diff 两处 permissions_data/admin codes | 一致 |

## 4. 范围控制（Minimal Change Guard）

本 Feature 改动文件白名单（15 个，14 改 + 1 新建）：

```text
.env
.env.example
apps/api/scripts/seed.py
apps/api/src/app/ai/mcp_server.py
apps/api/src/app/core/config.py
apps/api/src/app/core/rbac/checker.py
apps/api/src/app/modules/admin/router.py
apps/api/src/app/modules/ai/router.py
apps/api/src/app/modules/auth/router.py
apps/api/src/app/modules/booking/router.py
apps/api/src/app/modules/common/router.py
apps/api/src/app/modules/membership/router.py
apps/api/src/app/modules/teacher/router.py
apps/api/src/app/modules/tenant/router.py
apps/api/tests/conftest.py
apps/api/tests/integration/test_rbac_enforcement.py (new)
```

注意：工作区同时存在大量**与本 Feature 无关的历史未提交变更**（miniapp、membership service、ai runtime 等，来自 F1.2/F1.3/F3.1/F5.x 等先前 Feature 及未提交工作）。本 Feature 的 diff 审查只针对上表白名单文件，逐文件确认改动仅限装饰器/配置/种子/注释/测试，**无 Service 层业务逻辑改动、无 api-types 改动、无前端改动**。

## 5. 结论

静态验证全部通过，改动范围符合 plan 的 Exact Fix 与 Out of Scope 约束。
