---
alwaysApply: true
---

# 前后端 API 契约

## 唯一契约源

1. FastAPI OpenAPI Schema 是前后端接口的**唯一事实源**；`packages/api-types` 由 `pnpm gen:types` 从 OpenAPI 生成。
2. 禁止手改 `packages/api-types` 生成产物；后端变更接口后必须更新 OpenAPI 并重新生成类型。
3. 前端**禁止调用后端不存在的端点或方法**（曾出现 membership.ts 声明了后端不存在的 `DELETE /membership/cards/{id}`、`batch-delete`）：新增每个 API 方法前必须逐一核对路由真实存在。
4. 请求/响应 DTO 以后端 Pydantic 模型为准；前端不得在本地重复定义后端 DTO 类型，应从 `@dance-saas/api-client` 的导出或 `api-types` 引用。

## 请求约定

- 全部接口位于 `/api/v1` 前缀；后端 `redirect_slashes=False`，集合端点**不要加尾斜杠**（`/courses` ≠ `/courses/`）。
- Web 三端 baseURL 为相对路径 `/api/v1`（同源，Nginx/Vite 代理），**禁止硬编码绝对 URL**；小程序使用 `VITE_API_BASE_URL` 绝对地址（无同源能力）。
- 身份与租户通过请求头传递（`Authorization: Bearer`、`x-tenant-slug`），由各自 API 层拦截器统一注入；业务身份不得放进请求体由前端组装。

## 响应约定

统一信封：

```json
{ "code": 0, "msg": "success", "data": { } }
```

- 业务错误同时体现在 HTTP 状态码与响应体，前端不得只判断 HTTP 200。
- 后端错误处理必须通过统一异常体系返回信封，禁止向前端回传 traceback / 内部堆栈（实现见 `backend/fastapi.md`）。
- 401 处理已在两个 API 层实现：自动用 refresh_token 刷新并重放原请求，刷新失败清除登录态并跳转登录；业务代码不得另造一套刷新逻辑。

## 兼容性

- 新增可选字段属于兼容变更；删除字段、改类型、改语义属于破坏性变更，必须前后端同批修改并在同一变更中交付。
- 接口契约变更必须同步评估 4 个端（admin / student / teacher / miniapp）的影响面，即使结论是"不涉及"也要显式确认。
