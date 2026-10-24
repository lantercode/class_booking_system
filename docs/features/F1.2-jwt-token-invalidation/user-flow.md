# F1.2 — User Flow

> 本 Feature 为后端安全能力，无新 UI；以下为可观察的请求级流程，供测试用例映射。

## 主流程：登出即失效

1. 用户持有有效 access_token（T1）+ refresh_token（R1），正常访问受保护接口 → 200。
2. 客户端调用 `POST /auth/logout`（Authorization: Bearer T1，body 可选 refresh_token=R1）。
3. 服务端：T1 与 R1 均写入 `blacklist:`，T1 的 TTL=其剩余有效期，R1 保持 7 天默认。
4. 客户端再次持 T1 调用任意受保护接口（如 GET /auth/me）→ **401**，统一信封。
5. 客户端按既有拦截器用 R1 调 `/auth/refresh-token` → **401**（R1 已拉黑）。
6. 前端清除登录态并跳转登录页（现有行为，无前端改动）。

## 异常流程

| 场景 | 预期 |
|------|------|
| 登出时不带 Authorization 头 | 401（get_current_user 现有行为，登出端点本身需要登录） |
| 登出时 body 不含 refresh_token | access_token 仍被拉黑；接口返回 200"登出成功"（保持 refresh_token 可选语义） |
| 用已拉黑的 token 再次调 logout | 401（黑名单校验在端点逻辑之前） |
| 已过期的 token 调受保护接口 | 401"Token 已过期或无效"（decode 失败，行为不变，无需查黑名单） |
| 伪造/篡改 token | 401（decode 失败，行为不变） |
| 重复登出 | 幂等：SETEX 覆盖，200 |
| Redis 短暂不可用时持有效 token 访问 | fail-closed，认证失败（AuthException）；不允许放行 |
| 黑名单 token 访问可选认证端点（teacher 公开+登录增强接口） | 视为匿名：current_user=None，不报 401 |

## 边界状态

- **TTL 边界**：登出时 T1 剩余有效期恰好 ≤0（已过期但客户端未察觉）→ 不写黑名单，登出仍成功；该 token 本就无法通过解码。
- **多设备**：本 Feature 只撤销本次请求携带的 access_token；其他设备上的其他 token 不受影响（无会话维度，符合 Scope）。
- **登出后重新登录**：签发全新 token，新 token 不在黑名单，正常使用——黑名单键按 token 字符串区分，互不影响。

## Permission / Authentication

- logout 端点：必须已登录（现状如此，不变）。
- 黑名单校验属于认证（Authentication）层，不涉及 RBAC 授权；403 行为不在本 Feature 范围。
- `/api/v1/ai/chat` 经 `get_agent_runtime → get_current_user`，撤销后同样 401。

## Loading / Success / Error（接口语义）

- Success：logout 返回统一信封 `{code:0,msg:"登出成功"}`。
- Error：被撤销 token 的后续请求返回 401 统一信封，错误文案与现有 AuthException 一致（不暴露黑名单/Redis 细节）。
- 不适用 UI Loading/Empty 态（纯后端 Feature）。
