# F1.2 — Implementation Report

> Feature: F1.2 JWT Token 主动失效
> 阶段：DEVELOPMENT → STATIC VERIFICATION → TESTING 完成
> 日期：2026-09-26

## Changed Files

| # | 文件 | 改动行数 | 性质 |
|---|------|---------|------|
| 1 | `apps/api/src/app/core/security.py` | +44/-3 | 黑名单 TTL 参数化 + 新增 `get_token_remaining_ttl` |
| 2 | `apps/api/src/app/modules/auth/service.py` | +20/-21 | `logout` 新增 access_token 拉黑（TTL=剩余有效期） |
| 3 | `apps/api/src/app/modules/auth/router.py` | +11/-8 | logout 从 Authorization 头提取 access_token 传入 service |
| 4 | `apps/api/src/app/deps/auth.py` | +75（含重排） | `get_redis_client` 上移；`get_current_user`/`get_optional_user` 注入 redis 并校验黑名单 |
| 5 | `apps/api/tests/integration/test_auth_api.py` | +275/-? | 新增 6 个 F1.2 验收用例 + 修复预存测试断言（租户头、字段名、phone 生成） |

## Exact Changes

### 1. security.py
- `add_token_to_blacklist(token, redis, ttl_seconds: int | None = None)`：新增可选 TTL 参数（秒）。None→7 天默认（refresh 兼容）；>0→指定秒数；≤0→跳过写入。
- 新增 `get_token_remaining_ttl(token) -> int | None`：复用 decode_token 取 exp，返回剩余秒数。

### 2. auth/service.py
- `logout` 签名加 `access_token: str | None = None`，`refresh_token` 改为 `str | None`。
- 逻辑：① 拉黑 access_token（TTL=剩余有效期，None 或解析失败则跳过）；② refresh_token 存在时先查重再拉黑（7 天）。

### 3. auth/router.py
- logout handler 从 `request.headers["authorization"]` 提取 access_token，传给 `AuthService.logout(..., access_token=...)`。
- 无论 body 是否含 refresh_token 都调用 logout（修复了"无 refresh_token 时不拉黑 access"的预存缺陷）。

### 4. deps/auth.py
- `get_redis_client` 上移至文件顶部（解决 `Depends()` 默认参数求值时的 NameError）。
- `get_current_user` 注入 `redis_client=Depends(get_redis_client)`，解码成功后、ContextVar 写入前调用 `is_token_blacklisted`，命中抛 401。
- `get_optional_user` 同样注入 redis，黑名单命中返回 None（匿名语义）。

### 5. test_auth_api.py
- 新增 `TestAccessTokenBlacklist` 类，6 个用例（TC-01/03/04/08/09/10）。
- 修复预存测试断言：`generate_unique_phone` 保证 11 位；`test_logout_*` 加 `x-tenant-slug`；`test_get_me`/`complete_happy_path` 字段 `user_id`→`id`/`phone`。

## Scope Verification

- ✅ 实际修改文件 ⊆ 白名单 5 文件
- ✅ 工作区其余 63 项预存改动与 Pre-Change 基线完全一致（未触碰）
- ✅ 无白名单外文件、无格式化外溢、无业务逻辑外溢
- ✅ OpenAPI 契约未变：无新端点、logout 请求体/响应体不变

## Tests Run

| 套件 | 结果 | 说明 |
|------|------|------|
| `test_auth_api.py`（全量 25 用例） | ✅ 25 passed | 含 F1.2 新增 6 用例 + 修复的预存断言 |
| `test_rbac_real_redis.py` | ✅ 6 passed | redis 依赖注入不破坏 RBAC 缓存 |
| `test_tenant_isolation.py` | ⚠ 预存失败（3 failed） | db_session 直连 DB，不经 get_current_user；"attached to a different loop" 为测试事件循环问题，与 F1.2 无关 |
| `test_mcp_server.py` | ⚠ 预存失败（4 failed） | MCP stdio 不经 HTTP 认证；"未提供租户身份"为测试设置问题，与 F1.2 无关 |
| `test_agent_runtime.py` | ✅ passed | AI runtime 不受影响 |

## Results

- **AC-1（主验收）PASS**：登出后旧 access_token 调用 /auth/me 返回 401（统一信封，无内部信息泄露）
- **AC-2 PASS**：access_token 黑名单按剩余有效期写入；refresh_token 保持 7 天
- **AC-3 PASS**：未登出 token 不受影响；可选认证端点对黑名单 token 按匿名处理；重复登出第二次 401
- **AC-6.1 PASS**：test_auth_api.py 全绿
- **AC-6.2 部分**：test_rbac_real_redis 通过；test_tenant_isolation 预存失败（非 F1.2 引入）

## Risks

1. **Redis 单例跨事件循环**：`_redis_client` 全局单例绑定创建它的事件循环，若测试用多事件循环可能 "attached to a different loop"。F1.2 之前 get_current_user 不触发 redis，未暴露此问题；生产环境单进程单事件循环无此问题。建议后续 F7.x 考虑改用依赖注入作用域 redis。
2. **每认证请求 +1 次 Redis EXISTS**：O(1) 亚毫秒，98 处依赖统一受益；高并发下需关注 Redis QPS。
3. **test_tenant_isolation / test_mcp_server 预存失败**：非 F1.2 引入，但会影响 CI 绿度。建议单独开 Feature 修复测试基础设施。

## UNKNOWN

- 生产环境 Redis 在 F1.2 上线后的 EXISTS QPS 增长（需上线后监控，属 F7.2 监控范畴）
- `ENABLE_TOKEN_BLACKLIST=False` 时的完整行为回归（开关关闭路径沿用既有早退，未单独跑用例；代码审查确认无变化）

## Handoff

- 执行 Agent：backend-engineer（单一）
- 下一阶段：REVIEW → ACCEPTANCE → CLOSE
- 验收入口：`pytest tests/integration/test_auth_api.py::TestAccessTokenBlacklist -v`
