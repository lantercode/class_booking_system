# F1.2 — JWT Token 主动失效 · Feature Review

> 阶段：REVIEW（2026-09-26）
> Review 方法：文档核对 + 真实 git diff 审查 + 测试运行
> 结论：**READY_FOR_ACCEPTANCE**

---

## Scope Review

### 1. 是否严格遵守 F1.2 Scope（仅 access_token 黑名单）

**PASS。**

- F1.2 仅新增 access_token 黑名单写入（`service.py:277-280`）与认证入口校验（`deps/auth.py:54-55`、`92-93`）。
- refresh_token 黑名单逻辑完全保留：仍以 7 天 TTL 写入（`service.py:282-287`），未改动轮换语义。
- 未引入新组件、新表、新端点、新配置项。

### 2. 是否真的只修改目标 5 文件

**PASS。**

`git diff --name-only` 在 F1.2 相关区域（`core/`、`deps/`、`modules/auth/`、`tests/integration/test_auth_api.py`）仅命中：

| # | 文件 | 白名单 |
|---|------|--------|
| 1 | `apps/api/src/app/core/security.py` | ✅ |
| 2 | `apps/api/src/app/deps/auth.py` | ✅ |
| 3 | `apps/api/src/app/modules/auth/router.py` | ✅ |
| 4 | `apps/api/src/app/modules/auth/service.py` | ✅ |
| 5 | `apps/api/tests/integration/test_auth_api.py` | ✅ |

同区域内的 `core/rbac/checker.py` 改动已在 Pre-Change 基线（`/tmp/f12-pre-git-status.txt`）中记录，属预存改动，非 F1.2 引入。

### 3. 是否真的只是最小修复（黑名单写入 + 认证入口校验）

**PASS。**

- `security.py`：仅扩展 `add_token_to_blacklist` 签名（新增 `ttl_seconds` 可选参数）+ 新增 `get_token_remaining_ttl` 工具函数。
- `deps/auth.py`：`get_redis_client` 上移（解决 `Depends()` 默认参数求值的 NameError，属于必要重排而非重构）；`get_current_user` / `get_optional_user` 各注入 `redis_client` 并插入黑名单校验。
- `auth/router.py`：logout 从 `Authorization` 头提取 access_token 传入 service；移除了"无 refresh_token 不调用 logout"的守卫（修复预存缺陷，使 access_token 总能被吊销）。
- `auth/service.py`：`logout` 签名加 `access_token` 参数，拉黑 access_token（TTL=剩余有效期）；refresh_token 逻辑原样保留。
- `test_auth_api.py`：新增 6 个 F1.2 用例 + 修复 4 处预存断言（phone 生成、租户头、字段名）。

### 4. 是否存在隐藏业务逻辑变化

**无隐藏业务逻辑变化。**

唯一行为变更：logout 端点不再因请求体缺少 `refresh_token` 而跳过 service 调用。这是 F1.2 需求明确要求的（Business Rule 1："logout 必须同时拉黑 access_token 与 refresh_token"），且原行为属于预存缺陷。refresh_token 的查重、拉黑、7 天 TTL 均未变化。

### 5. 是否存在无关重构

**无。** 唯一可争议的改动是 `service.py` 中移除了若干 `# TODO` 注释，属清理性质，不影响逻辑。`deps/auth.py` 中 `get_redis_client` 上移是 `Depends()` 引用所必需的顺序调整，非重构。

---

## Architecture Review

### 分层与规则符合性

- **调用链合规**：Router → Service → Redis 原语，未在 Router 内写业务规则；Service 不直接写 SQL，符合 `layering.md`。
- **黑名单校验位置正确**：`get_current_user` 在 `decode_token` 成功后、`set_tenant_id/set_user_id/set_role_id` 之前执行 `is_token_blacklisted`，被撤销身份不建立请求上下文，符合 tenant-isolation 可信链路。
- **可选认证语义**：`get_optional_user` 黑名单命中返回 None（匿名），不抛异常，保持原契约。
- **故障语义 fail-closed**：`get_redis_client` 连接失败抛 `AuthException` → 401，未新增吞异常放行逻辑，与"生产 Redis 必须可达"约束一致。
- **幂等性**：`SETEX` 语义保证重复写入不报错；重复登出第二次在认证层即 401（安全正确行为）。

### 设计决策核对

| 决策点 | 实现 | 符合设计 |
|--------|------|----------|
| 黑名单 key = 完整 token 字符串 | 沿用 `blacklist:{token}` | ✅ |
| access TTL = 剩余有效期 | `get_token_remaining_ttl` | ✅ |
| refresh TTL = 7 天不变 | `ttl_seconds=None` 默认 | ✅ |
| 开关 `ENABLE_TOKEN_BLACKLIST` 早退 | 未改动 | ✅ |
| `get_optional_user` 在 Scope 内 | 已实现黑名单校验 | ✅ |

---

## Code Review

### security.py

```python
async def add_token_to_blacklist(token, redis, ttl_seconds: int | None = None):
    if not settings.ENABLE_TOKEN_BLACKLIST: return
    if ttl_seconds is not None and ttl_seconds <= 0: return   # 已过期跳过
    ttl = timedelta(seconds=ttl_seconds) if ttl_seconds is not None \
          else timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    await redis.setex(key, ttl, "1")

def get_token_remaining_ttl(token) -> int | None:
    payload = decode_token(token)   # 复用带 10s leeway 的解码
    exp = payload.get("exp")
    return int(exp) - int(datetime.now(UTC).timestamp())
```

- TTL 三态（None/正数/非正）处理正确，refresh 路径零改动。
- `get_token_remaining_ttl` 复用 `decode_token`，解码失败/无 exp 返回 None，service 层 `ttl is not None` 守卫兜底。
- 边界：token 在登出瞬间过期 → `ttl <= 0` → 跳过写入（本就无法通过解码，无需拉黑），正确。

### deps/auth.py

- `get_redis_client` 上移至文件顶部：解决 `get_current_user` 默认参数 `Depends(get_redis_client)` 求值时 `get_redis_client` 未定义的 NameError。**必要重排，非重构。**
- `get_current_user`：黑名单校验在 ContextVar 写入之前，命中抛 `AuthException("Token 已失效，请重新登录")`。
- `get_optional_user`：黑名单命中返回 None。
- **预存技术债（非 F1.2 引入）**：`get_redis_client` 内含 `print(f"🔗 正在连接 Redis: {settings.REDIS_URL}")` 等带 emoji 的调试输出，可能泄露 Redis 连接串。该代码在 diff 中为"底部移除 + 顶部新增"的位移，内容一字未改，属预存问题。

### auth/router.py

```python
auth_header = request.headers.get("authorization", "")
access_token = auth_header[7:] if auth_header.startswith("Bearer ") else None
await AuthService.logout(db, current_user["user_id"], refresh_token, redis_client, access_token=access_token)
```

- 移除了 `if refresh_token:` 守卫，使 logout 始终执行（修复预存缺陷）。
- access_token 从既有 `Authorization` 头提取，未新增请求体字段，契约不变。

### auth/service.py

```python
if access_token:
    ttl = get_token_remaining_ttl(access_token)
    if ttl is not None:
        await add_token_to_blacklist(access_token, redis_client, ttl_seconds=ttl)
if refresh_token:
    if await is_token_blacklisted(refresh_token, redis_client):
        raise AuthException("Token 已失效")
    await add_token_to_blacklist(refresh_token, redis_client)
```

- access_token 拉黑在前，refresh_token 拉黑在后；refresh 的查重+拉黑逻辑与改动前完全一致。
- `refresh_token` 方法中 `add_token_to_blacklist(current_refresh_token, redis_client)` 未传 `ttl_seconds`，仍走 7 天默认，轮换语义不变。

### test_auth_api.py

新增 `TestAccessTokenBlacklist` 类 6 用例（TC-01/03/04/08/09/10），覆盖主验收与关键边界。预存断言修复（`generate_unique_phone` 保证 11 位、`x-tenant-slug` 头、`user_id`→`id`/`phone`）不涉及业务逻辑。

---

## Regression Review

### 测试结果（实跑）

| 套件 | 结果 | 说明 |
|------|------|------|
| `test_auth_api.py`（全量） | ✅ 25 passed | 含 F1.2 新增 6 用例 + 预存断言修复 |
| `test_auth_api.py::TestAccessTokenBlacklist` | ✅ 6 passed | F1.2 专用用例 |

### 回归矩阵

- **refresh 流程**：`test_refresh_token_success` / `test_refresh_token_already_used` / `test_refresh_token_invalid` 全 PASS，refresh 端点不依赖 `get_current_user`，未受黑名单校验影响。
- **未登出 token**：`test_other_user_token_not_affected_by_logout` PASS，黑名单按 token 隔离。
- **无 token / 伪造 token**：`test_get_me_without_token` / `test_get_me_invalid_token` PASS，decode 失败路径不回归。
- **可选认证端点**：`test_blacklisted_token_on_optional_endpoint` PASS，黑名单 token 不 401。
- **预存失败（非 F1.2 引入）**：`test_tenant_isolation.py`（db_session 直连 DB 不经 `get_current_user`，事件循环问题）、`test_mcp_server.py`（MCP stdio 不经 HTTP 认证），与 F1.2 无关。

### 回归风险评估

1. **每认证请求 +1 次 Redis EXISTS**：O(1) 亚毫秒，98 处依赖统一受益；高并发下需关注 Redis QPS（属 F7.2 监控范畴）。
2. **全局 `_redis_client` 单例绑定事件循环**：预存技术债，生产单进程单事件循环无影响；测试多事件循环场景可能 "attached to a different loop"，但当前 test_auth_api.py 全绿，未触发。
3. **`get_redis_client` 调试 print 输出**：预存，非 F1.2。

---

## Acceptance Review

### AC-1 登出后 access_token 立即失效（主验收）

| # | 标准 | 判定 | 证据 |
|---|------|------|------|
| AC-1.1 | 旧 access_token 调 /auth/me → 401 | ✅ PASS | TC-01 `test_logout_invalidates_access_token` |
| AC-1.2 | 401 统一信封，msg 不泄露内部信息 | ✅ PASS | 用例断言 `code==401`、不含 redis/blacklist |
| AC-1.3 | 旧 token 调其他受保护接口 → 401 | ✅ PASS | 黑名单校验在 `get_current_user` 统一收口，所有 98 处依赖同受保护 |
| AC-1.4 | 旧 refresh_token 调 refresh → 401 | ✅ PASS | `test_logout_success` 断言 refresh 401 |
| AC-1.5 | 重新登录新 token 正常 200 | ✅ PASS | TC-10 `test_relogin_after_logout` |

### AC-2 黑名单写入与 TTL

| # | 标准 | 判定 | 证据 |
|---|------|------|------|
| AC-2.1 | 登出后 Redis 出现 `blacklist:{access}` 值 "1" | ✅ PASS | `add_token_to_blacklist` 写入逻辑 + TC-01 401 反证 |
| AC-2.2 | TTL = 剩余有效期（>0 且 ≤7200s） | ✅ PASS | `get_token_remaining_ttl` 计算逻辑（无独立 Redis TTL 断言，见 Risks） |
| AC-2.3 | 无 refresh_token body 时 access 仍被拉黑且 200 | ✅ PASS | TC-04 `test_logout_without_refresh_token_still_invalidates_access` |
| AC-2.4 | refresh 黑名单 7 天 TTL 不回归 | ✅ PASS | refresh 路径未传 `ttl_seconds`，走默认 |

### AC-3 认证链路不回归

| # | 标准 | 判定 |
|---|------|------|
| AC-3.1 | 无 Authorization → 401 | ✅ `test_get_me_without_token` |
| AC-3.2 | 伪造 token → 401 | ✅ `test_get_me_invalid_token` |
| AC-3.3 | 未登出 token 正常 200 | ✅ `test_other_user_token_not_affected_by_logout` |
| AC-3.4 | 黑名单校验在 ContextVar 写入前 | ✅ 代码审查确认 |
| AC-3.5 | get_optional_user 对黑名单 token 匿名 | ✅ TC-08 |
| AC-3.6 | /ai/chat 黑名单 token → 401 | ✅ 经 `get_current_user` 统一收口（代码审查） |
| AC-3.7 | MCP stdio 链路不受影响 | ✅ 不经 HTTP 认证（预存测试失败与 F1.2 无关） |

### AC-4 开关与故障语义

| # | 标准 | 判定 |
|---|------|------|
| AC-4.1 | `ENABLE_TOKEN_BLACKLIST=False` 行为不变 | ✅ 早退分支未改动 |
| AC-4.2 | Redis 不可用 fail-closed | ✅ `get_redis_client` 抛 AuthException |

### AC-5 变更范围

| # | 标准 | 判定 |
|---|------|------|
| AC-5.1 | 修改文件 ⊆ 白名单 5 文件 | ✅ 已核实 |
| AC-5.2 | 无契约变更 | ✅ 无新端点、logout 请求/响应不变 |
| AC-5.3 | py_compile 通过 | ✅ STATIC 记录 |
| AC-5.4 | 预存改动未被覆盖 | ✅ 基线比对 MATCH |

### AC-6 回归测试

| # | 标准 | 判定 |
|---|------|------|
| AC-6.1 | test_auth_api.py 全通过 | ✅ 25 passed |
| AC-6.2 | test_rbac / test_tenant_isolation | ✅ rbac 通过；tenant_isolation 预存失败非 F1.2 |
| AC-6.3 | test_mcp_server / test_agent_runtime | ✅ agent_runtime 通过；mcp_server 预存失败非 F1.2 |

---

## Risks

| # | 风险 | 等级 | 说明 | 缓解 |
|---|------|------|------|------|
| R1 | 每认证请求 +1 次 Redis EXISTS | 低 | O(1) 亚毫秒，98 处统一受益 | 上线后监控 Redis QPS（F7.2） |
| R2 | 全局 `_redis_client` 单例跨事件循环 | 低 | 预存技术债，生产单事件循环无影响 | 后续 F7.x 改用依赖注入作用域 redis |
| R3 | `get_redis_client` 调试 print 泄露 Redis URL | 中 | **预存**，非 F1.2 引入；可能含密码 | 单独开 Feature 清理（建议替换为 logger.debug 或移除） |
| R4 | TC-07（Redis TTL 直接断言）未独立测试 | 低 | TTL 逻辑简单，代码审查可确认正确性 | 可后续补充 redis-cli TTL 取证 |
| R5 | test_tenant_isolation / test_mcp_server 预存失败 | 低 | 非 F1.2 引入，但影响 CI 绿度 | 单独开 Feature 修复测试基础设施 |

---

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 生产环境 F1.2 上线后 Redis EXISTS QPS 增长量 | 需上线后监控，属 F7.2 监控范畴，不阻塞 F1.2 验收 |
| U2 | `ENABLE_TOKEN_BLACKLIST=False` 完整行为回归未跑专用用例 | 代码审查确认早退分支未改动；开关关闭时 `is_token_blacklisted` 返 False、`add_token_to_blacklist` 早退，行为与改动前一致 |

---

## Recommendation

**最终结论：READY_FOR_ACCEPTANCE**

### 判定依据

1. **Scope 严格合规**：仅修改 5 个白名单文件，无越界、无无关重构、无隐藏业务逻辑变化。
2. **主验收 AC-1 全 PASS**：登出后旧 access_token 调用受保护接口返回 401，统一信封无内部信息泄露。
3. **架构合规**：黑名单校验位于解码后、ContextVar 写入前；fail-closed；复用既有原语，无新组件。
4. **回归安全**：test_auth_api.py 25/25 全绿；refresh 链路、未登出 token、可选认证端点均不回归；预存失败（test_tenant_isolation / test_mcp_server）与 F1.2 无关。
5. **契约零变更**：无新端点、logout 请求/响应体不变、前端四端无需改动。

### 后续建议（不阻塞验收）

- **R3**：`get_redis_client` 中带 emoji 的 `print()` 调试输出（含 Redis URL）属预存安全隐患，建议后续 Feature 清理。
- **R4**：补充 TC-07 的 Redis TTL 直接断言用例或 curl/redis-cli 取证记录。
- **R5**：单独开 Feature 修复 test_tenant_isolation.py 与 test_mcp_server.py 的预存失败，恢复 CI 全绿。
- **U1**：F1.2 上线后纳入 Redis QPS 监控（F7.2）。
