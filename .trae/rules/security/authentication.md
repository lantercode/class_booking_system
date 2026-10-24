---
alwaysApply: true
---

# 认证（Authentication）

## JWT 双 Token

- 敏感端点必须依赖 `Depends(get_current_user)`；未认证请求不得触达业务逻辑。
- Access Token：JWT（HS256），有效期 `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`；Refresh Token：有效期 `JWT_REFRESH_TOKEN_EXPIRE_DAYS`。
- Token 唯一性由 `iat`（微秒）+ `jti`（UUIDv4）保证；登出 / 轮换时将 `jti` 加入 Redis 黑名单，TTL 等于 token 剩余有效期，key 前缀 `blacklist:`。
- 生产环境 Redis 必须可达（应用 `lifespan` 在 Redis 不可达时抛错）；黑名单、限流、会话、RBAC 缓存均依赖它。

## 密钥与机密

- 所有机密（JWT 密钥、`WECHAT_SECRET`、数据库/Redis 口令等）只能来自环境变量 / `.env.*`（`.env.prod`、`.env.production` 已 gitignore），**禁止硬编码**在源码或提交进仓库。
- 禁止在任何响应、日志、AI 对话内容中暴露 Token、密钥、内部数据库 URL、堆栈细节。
- AI 接口同样要求登录态：`/api/v1/ai/*` 通过 `get_current_user` 注入用户身份（AI 侧的身份注入规则见 `ai/ai-architecture.md`）。

## 客户端配合（约束后端设计时必须成立）

- 401 响应由前端 API 层统一触发 refresh → 重放 → 失败则清登录态；后端 refresh 端点不得要求额外业务权限，且刷新接口本身不参与 401 重试循环。
