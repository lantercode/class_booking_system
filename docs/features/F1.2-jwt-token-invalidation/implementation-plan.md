# F1.2 — JWT Token 主动失效 · 实施方案

> Feature ID：F1.2
> 日期：2026-09-26
> 性质：最小补丁（logout 写入 + 认证入口校验），复用既有 Redis 黑名单原语，不引入新组件
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

### 问题 1：登出只拉黑 refresh_token，access_token 仍可使用

- `modules/auth/router.py:76-99` logout：依赖 `get_current_user`；只从 JSON body 取 `refresh_token`（可选）；未读取 Authorization 头中的 access_token。
- `modules/auth/service.py:253-288` `AuthService.logout`：仅 `add_token_to_blacklist(refresh_token, redis_client)`（L286）。
- 后果：用户登出后，access_token 在最长 120 分钟有效期内仍可正常访问全部 98 处受保护接口，违反"登出/轮换时将 token 加入黑名单"的认证规则。

### 问题 2：认证入口不校验黑名单

- `app/deps/auth.py:11-31` `get_current_user`：头校验 → `decode_token` → None 则 401 → ContextVar 写入。**无 Redis 依赖、无黑名单校验**。
- `get_optional_user`（L34-61）：同理解码，失败返回 None；同样无黑名单校验。
- 后果：已被加入黑名单的 token（如登出后的 refresh_token）在 access_token 路径上无法被拦截。

### 问题 3：黑名单 TTL 硬编码 7 天

- `core/security.py:113-127` `add_token_to_blacklist`：`ttl = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)` 硬编码 7 天。
- 后果：access_token 若被拉黑，其黑名单 key 会残留 7 天而非 access_token 实际剩余有效期（最长 120 分钟），造成 Redis 空间浪费。

---

## Affected Files

| # | 文件 | 改动内容 |
|---|------|---------|
| 1 | `apps/api/src/app/core/security.py` | `add_token_to_blacklist` 新增可选 `ttl_seconds` 参数；新增 `get_token_remaining_ttl` |
| 2 | `apps/api/src/app/modules/auth/service.py` | `logout` 新增 access_token 拉黑（TTL=剩余有效期） |
| 3 | `apps/api/src/app/modules/auth/router.py` | logout 从 Authorization 头提取 access_token 传入 service |
| 4 | `apps/api/src/app/deps/auth.py` | `get_current_user` / `get_optional_user` 注入 redis 并校验黑名单 |
| 5 | `apps/api/tests/integration/test_auth_api.py` | 新增 6 个 F1.2 验收用例 |

---

## Exact Fix

### 1. security.py

- `add_token_to_blacklist(token, redis, ttl_seconds: int | None = None)`：新增可选 TTL 参数（秒）。
  - `ttl_seconds is None` → 维持现有 7 天默认（refresh 路径零改动）
  - `ttl_seconds <= 0` → 跳过写入（已过期 token 无需拉黑）
- 新增 `get_token_remaining_ttl(token: str) -> int | None`：复用 `decode_token`；取 `exp` − `now`；解码失败或无 exp 返回 None。

### 2. auth/service.py

- `logout` 签名增加 `access_token: str | None = None`。
- 逻辑：① 计算 `ttl = get_token_remaining_ttl(access_token)`；当 `ttl is not None and ttl > 0` 时拉黑 access_token；② refresh_token 存在时拉黑（7 天，现有逻辑）。

### 3. auth/router.py

- logout handler 内从 `request.headers.get("authorization", "")` 提取并去 `Bearer ` 前缀得到 access_token，传入 `AuthService.logout(...)`。

### 4. deps/auth.py

- `get_current_user` 增加参数 `redis_client=Depends(get_redis_client)`；在 payload 解码成功后、ContextVar 写入前插入 `is_token_blacklisted` 校验，命中抛 401。
- `get_optional_user` 同样注入 redis：黑名单命中返回 None（匿名语义）。
- `get_redis_client` 上移至文件顶部（解决 `Depends()` 默认参数求值时的 NameError）。

### 5. test_auth_api.py

- 新增 `TestAccessTokenBlacklist` 类，6 个用例（登出后旧 token 401、未登出不受影响、无 refresh_token 登出仍吊销 access、可选认证端点匿名处理、重复登出第二次 401、重新登录获得新 token）。

---

## Why This Fix Is Sufficient

1. access_token 黑名单按剩余有效期写入，登出后立即失效，TTL 自然清理不残留。
2. 黑名单校验位于 ContextVar 写入之前，被撤销身份不建立租户/用户上下文，符合租户隔离可信链路。
3. refresh_token 黑名单行为（7 天 TTL、一次性使用）完全不变，refresh 链路不受影响。
4. `get_optional_user` 对黑名单 token 按匿名处理，保持其"不抛异常"的契约。

---

## Verification Plan

| AC 编号 | 验证方式 |
|---------|---------|
| AC-1.1 ~ AC-1.5 | 集成测试 `test_auth_api.py::TestAccessTokenBlacklist` + curl |
| AC-2.1 ~ AC-2.4 | redis-cli 查 key + TTL；代码审查 |
| AC-3.1 ~ AC-3.7 | 集成测试 + test_tenant_isolation 回归 + curl |
| AC-4.1 ~ AC-4.2 | 代码审查（沿用既有早退分支 / fail-closed 语义） |
| AC-5.1 ~ AC-5.4 | minimal-change-guard verify-scope + py_compile + 基线比对 |
| AC-6.1 ~ AC-6.3 | pytest 全量回归 |

---

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | Redis EXISTS 在 CI 环境是否有真实 Redis 服务 | 现有 integration 测试本就要求 Redis，本 Feature 不新增环境要求 |
| U2 | 生产部署是否有已登出但依赖旧 token 的长连接客户端 | 无 SSE/WebSocket 受保护长连接（/ai/chat 为一次性 JSON），无影响 |
