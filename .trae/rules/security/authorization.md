---
alwaysApply: true
---

# 授权（Authorization / RBAC）

## 强制使用 RBAC 装饰器

- 受保护端点使用 `@require_permissions("resource:action")` 或 `@require_roles(...)`；标准 action：`create / read / update / delete`，外加 `role:assign`、`user:reset_password` 等。
- 新增管理类 / 写操作端点**必须显式声明权限**，不得裸奔，也不得依赖全局放行开关。
- 装饰器从函数参数取 `db`、`current_user`、`redis_client`；被装饰函数签名必须包含这些参数，否则触发 KeyError。

## 权限缓存

- 权限按 角色 存储，缓存 Key：`perms:{tenant_id}:{user_id}`，TTL 300s。
- 角色 / 权限变更后必须使对应用户缓存失效。

## 禁止 bypass

- `PERMISSION_CHECK_BYPASS=True` 是待偿还的技术债务（见 `project_rules.md` 附录），**不是可依赖的行为**：新代码一律按真实权限校验编写，不得新增类似的放行开关，不得因为"当前 bypass"而省略 `@require_permissions`。
- AI MCP Tool 必须在认证之后独立完成授权判断，四关顺序见 `ai/mcp.md`。
