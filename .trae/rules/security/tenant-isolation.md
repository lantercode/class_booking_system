---
alwaysApply: true
---

# 多租户隔离

## 三层隔离（全部保留，不得绕过）

1. **Middleware**（`tenant_middleware.py`，纯 ASGI）：从 `x-tenant-id` / `x-tenant-slug` 头识别租户。
2. **ContextVar**（`tenant_context.py`）：`set_tenant_id` / `get_tenant_id` 保存当前请求租户。
3. **ORM 事件**（`tenant_query.py`，`do_orm_execute`）：对租户表查询自动注入 `WHERE tenant_id = :val`。

## 强制规则

- 持有租户数据的 Repository **必须继承 `TenantAwareRepository[Model]`**；禁止编写绕过租户注入的裸查询（原生 SQL、跨租户联表尤其要审查）。
- **绝不信任请求体里的 `tenant_id`**；业务数据的 `tenant_id` 一律取自已验证的 ContextVar。Middleware 必须校验该租户存在且 `status=ACTIVE` 后才允许入站。
- 租户跳过白名单（docs / health / 注册登录等）保持最小集合；**禁止为调试方便扩大跳过路径**（现存 `/api/v1/courses` 通配跳过是债务，见 `project_rules.md` 附录，新代码不得效仿）。
- 同一 Repository 方法内不要重复手工叠加 `tenant_id` 条件与自动注入对抗；如确需手动查询，需注释说明原因。

## 后台 / 定时任务

- APScheduler 任务运行在独立线程，ContextVar 为空：必须按租户循环、在处理前 `set_tenant_id(tenant_id)`，否则查不到数据或退化为全表扫描。
- 任务中新建的独立会话同样遵守此要求。

## AI / MCP

- 每个 MCP Tool 的数据访问都必须经过 Tenant Validation（四关之一，见 `ai/mcp.md`）；租户身份来自 Runtime 注入的可信上下文，不接受 LLM 或前端传入的 tenant_id。
