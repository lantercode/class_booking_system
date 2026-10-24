# F1.1 — RBAC 权限校验真实生效 · 需求文档

> Feature ID：F1.1
> 来源：`docs/delivery/feature-backlog.md` Epic 1 / Feature 1.1
> 阶段：Phase 1（安全基线）
> 状态：已交付
> 生成日期：2026-09-27

---

## 1. Goal

所有受保护端点执行真实权限校验，杜绝越权操作。关闭技术债务性质的 `PERMISSION_CHECK_BYPASS` 全局放行开关，补全所有缺失的 RBAC 装饰器，删除无认证的调试端点。

## 2. Problem

当前系统 RBAC 体系（`@require_permissions` / `@require_roles` 装饰器、`checker.py`、Redis 权限缓存）已完整实现，但存在三类安全缺口：

| # | 缺口 | 位置 | 影响 |
|---|------|------|------|
| 1 | `PERMISSION_CHECK_BYPASS = True` 硬编码 | `apps/api/src/app/core/rbac/checker.py:37-39`，4 处短路（check_permission / check_permissions / check_role / check_roles） | **所有**权限校验被全局跳过，任何登录用户可执行任意操作（如学员可删课、重置他人密码） |
| 2 | 5 个 router 缺失 RBAC 装饰器 | `ai/router.py`、`common/router.py`、`tenant/router.py`、`teacher/router.py`、`auth/router.py`；`booking/router.py` 3 个写端点、`membership/router.py` 2 个学员端点 | 关闭 bypass 后这些端点仍无授权拦截 |
| 3 | 无认证调试端点泄露 | `common/router.py` 的 `GET /test-token`（**无需认证即可生成任意用户 JWT**，含 admin） | 严重认证绕过漏洞 |

此外，种子数据中 admin 角色缺少 7 个已被装饰器引用的权限（`course:delete`、`user:delete`、`user:reset_password`、`classroom:delete`、`role:create`、`role:update`、`role:delete`），且 `admin:all` / `super:manage` 两个权限码在权限表中不存在；关闭 bypass 后 admin 调用这些端点会返回 403。

## 3. User Story

- 作为**平台运营方**，我希望所有受保护接口都执行真实权限校验，以便学员无法通过直接调用 API 执行管理员操作。
- 作为**管理员**，我希望关闭放行开关后我的日常管理操作（删课、重置密码、角色管理等）不受影响。
- 作为**安全负责人**，我希望无认证的 token 生成调试端点被移除，杜绝认证绕过。

## 4. Scope

按依赖顺序的 4 项任务：

| # | 任务 | 内容 |
|---|------|------|
| T1.1.1 | 补齐权限数据与种子 | `scripts/seed.py` 与 `tests/conftest.py` 同步新增权限 `admin:all`、`super:manage`；admin 角色补 7 个权限；修复 `admin/router.py` 两处错误装饰器（`batch_delete_users` 引用了不存在的 `security_admin` 角色且 require_all=True；`GET /admin/settings` 装饰器与补 `db` 参数） |
| T1.1.2 | 补全缺失 RBAC 装饰器 + 清理调试端点 | `common/router.py` 删除 `test_exception`/`test_auth`/`test_generate_token` 三个端点，`upload_image` 加角色校验；`ai/router.py` 的 `GET /ai/intents` 加认证；`tenant`/`teacher`/`auth`/`booking`/`membership` 共 9 个端点加 `@require_roles` |
| T1.1.3 | 关闭 PERMISSION_CHECK_BYPASS | `core/config.py` 新增 `PERMISSION_CHECK_BYPASS: bool = False` 配置项；`checker.py` 移除硬编码改为运行时读取配置；`.env` / `.env.example` 新增配置；`ai/mcp_server.py` 注释更新 |
| T1.1.4 | RBAC 集成测试 | 新增 `tests/integration/test_rbac_enforcement.py`，覆盖学员 403、admin 通过、无 token 401、调试端点 404、ai/intents 认证等场景 |

## 5. Out of Scope

以下内容**明确不在**本 Feature 内：

- 不新增权限模型、不重构 RBAC 架构（装饰器、checker、缓存机制保持不变）
- 不修改 Service 层任何业务逻辑
- 不修改 `packages/api-types`（无 OpenAPI 契约变更；接口路径/方法不变，只加装饰器）
- 前端四端不做任何改动
- MCP Tool 层细粒度授权（Feature 5.2）
- `ai/router.py` `get_supported_intents` 访问 `IntentRecognizer.intents` 的预存 500 bug（登记为技术债 D-F1.1-1）
- `test_tenant_isolation.py` / `test_mcp_server.py` 预存失败（3+4 个，与 F1.1 无关）
- 存量数据库的权限升级脚本（seed.py 的"已存在则跳过"逻辑导致旧库需手工补权限，见 Risks）

## 6. User Roles

| 角色 | 说明 |
|------|------|
| super_admin | 超级管理员，拥有全部权限 |
| admin | 租户管理员，本 Feature 为其补齐 7 个缺失权限 |
| teacher | 教师，可访问 `/teachers/me` 等教师端点；**不可**访问 booking 创建（学员专属） |
| student | 学员，可访问 booking/membership 学员端点；**不可**访问任何 `/admin/*`、`/users/*`、teacher 端点 |

## 7. Business Rules

- 权限校验链路不变：装饰器（从 kwargs 取 `db`/`current_user`/`redis_client`）→ `checker.py` → Redis 缓存（`perms:{tenant_id}:{user_id}`，TTL 300s）→ DB 查询。
- `PERMISSION_CHECK_BYPASS` 默认值必须为 `False`；该开关仅允许本地调试临时置 True，禁止在任何部署环境开启。
- 装饰器函数签名必须含 `db`（及按需 `redis_client`），否则装饰器取不到会话导致校验异常返回 403（本 Feature 在 `admin/settings` 端点修复了一个此类隐藏缺陷）。
- 业务身份（user_id / tenant_id）只来自 `get_current_user` 注入的 JWT payload，不接受请求体传入。

## 8. Dependencies

| 依赖 | 状态 |
|------|------|
| 前置 Feature | F1.2（JWT 黑名单）已交付，本 Feature 复用其认证链路 |
| 后端 / 数据库 / 契约变更 | 无 Schema 变更；种子数据（permissions/role_permissions 行）变更仅通过 seed 脚本与测试 conftest 落地 |
| 外部服务 | Redis 必须可用（权限缓存与 token 黑名单依赖；生产环境已强制） |
| 被依赖方 | 前端四端无改动需求（401/403 处理已在 API 客户端层实现） |

## 9. Risks

| 风险 | 等级 | 说明与缓解 |
|------|------|-----------|
| 存量数据库不会自动获得新权限（seed.py L100-105 "已存在则跳过"） | 高 | 升级存量环境时需手工执行 INSERT 补 `admin:all`/`super:manage` 权限与 admin 角色的 7 个权限关联，或清库重 seed；release-note 中给出 SQL |
| 权限缓存 300s 导致权限变更延迟生效 | 低 | 既有行为；角色/权限变更接口已有缓存失效逻辑 |
| 关闭 bypass 后若遗漏某个端点的装饰器，会造成该端点仍裸奔（但本 Feature 已全量审计 13 个 router） | 中 | 集成测试覆盖代表性端点；后续 code review 保持对新端点的装饰器强制检查 |
| 前端依赖了被删调试端点 | 低 | 已 grep 四端代码确认无引用；`test-token` 等端点本就是后端调试残留 |

---

## 附：现状证据（审计快照，2026-09-27）

```text
apps/api/src/app/core/rbac/checker.py:37-39
    # 临时：开发阶段跳过权限检查（生产环境必须关闭）
    PERMISSION_CHECK_BYPASS = True
    # L203 / L251 / L295 / L360 共 4 处 if PERMISSION_CHECK_BYPASS: return True

apps/api/src/app/modules/common/router.py
    @router.get("/test-token")   # 无认证，可生成任意用户 JWT（严重漏洞）
    @router.get("/test-exception")
    @router.get("/test-auth")

apps/api/src/app/modules/admin/router.py:473
    @require_roles("super_admin", "security_admin", require_all=True)  # security_admin 不存在 → 无人能通过

apps/api/scripts/seed.py（permissions_data 缺 admin:all / super:manage；
    admin_permission_codes 缺 course:delete / user:delete / user:reset_password /
    classroom:delete / role:create / role:update / role:delete）
```
