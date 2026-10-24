# F1.2 — Acceptance Criteria

> 每条可独立判定 PASS / FAIL / BLOCKED / UNKNOWN。
> 主 AC 为 AC-1；全部 AC 通过方可进入 REVIEW / ACCEPTANCE。

## AC-1 登出后 access_token 立即失效（主验收标准）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-1.1 | 登出后，旧 access_token 调 `GET /api/v1/auth/me` 返回 **HTTP 401** | TC-01 / curl |
| AC-1.2 | 401 响应为统一信封（code/msg/data），且 msg 不泄露 Redis、黑名单、堆栈等内部信息 | TC-01 |
| AC-1.3 | 登出后旧 access_token 调**任意其他**受保护接口（至少抽测 1 个业务端点，如 GET /bookings）同样 401 | curl 抽测 |
| AC-1.4 | 登出后旧 refresh_token 调 `/auth/refresh-token` 返回 401（无法换发新 token） | TC-02 |
| AC-1.5 | 重新登录获得的新 access_token 正常 200 | TC-10 |

## AC-2 黑名单写入与 TTL

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-2.1 | 登出时 Redis 出现 `blacklist:{access_token}`，值为 "1" | TC-07 / redis-cli |
| AC-2.2 | 该 key 的 TTL 等于 access_token 剩余有效期（>0 且 ≤7200 秒，误差 ≤5s） | TC-07 |
| AC-2.3 | 登出请求体不含 refresh_token 时，access_token 仍被拉黑且接口返回 200 | TC-04 |
| AC-2.4 | refresh_token 黑名单行为不回归（仍以 7 天 TTL 写入） | 现有 refresh 用例 + 代码审查 |

## AC-3 认证链路行为不回归

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-3.1 | 未携带 Authorization 头访问受保护接口 → 401 | TC-05 |
| AC-3.2 | 伪造/篡改 token → 401（decode 失败路径） | TC-06 |
| AC-3.3 | 未登出用户的正常请求 → 200，且其他用户登出不影响其会话 | TC-03 |
| AC-3.4 | 黑名单校验在 ContextVar 写入之前（被撤销 token 不建立租户/用户上下文） | 代码审查 + test_tenant_isolation 回归 |
| AC-3.5 | `get_optional_user`（teacher 端点）对黑名单 token 按匿名处理，不返回 401、不泄露身份 | TC-08 |
| AC-3.6 | AI 端点 `/api/v1/ai/chat` 使用黑名单 token → 401 | curl 取证 |
| AC-3.7 | MCP stdio Tool 直调链路不受影响 | test_mcp_server.py 通过 |

## AC-4 开关与故障语义

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-4.1 | `ENABLE_TOKEN_BLACKLIST=False` 时行为与改动前完全一致（函数早退，不查不写） | 代码审查（沿用既有早退分支）+ 可选 monkeypatch 用例 |
| AC-4.2 | Redis 不可用时认证 fail-closed（不放行），且错误响应不泄露内部信息 | 代码审查（依赖既有 get_redis_client AuthException 语义） |

## AC-5 变更范围（静态）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-5.1 | 实际修改文件 ⊆ Scope 白名单 5 文件（security.py / auth service / auth router / deps.auth / test_auth_api.py） | minimal-change-guard verify-scope.sh |
| AC-5.2 | 无契约变更：无新端点、logout 请求体与响应体不变 | OpenAPI diff 审查 |
| AC-5.3 | 每个修改的 Python 文件通过 `python3 -m py_compile` | STATIC 记录 |
| AC-5.4 | 工作区 63 项预存改动未被覆盖/清理/混入本 Feature 提交 | 修改前后哈希对比（/tmp/f12-pre-hashes.txt） |

## AC-6 回归测试

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-6.1 | `tests/integration/test_auth_api.py` 全部通过（含新增用例） | pytest |
| AC-6.2 | test_rbac_real_redis / test_tenant_isolation 通过 | pytest |
| AC-6.3 | test_mcp_server / test_agent_runtime 通过 | pytest |

## 判定规则

- 任何 AC-1.x FAIL → Feature 整体 FAIL
- AC-2 ~ AC-6 中出现 FAIL → NEEDS_FIX 回到 DEVELOPMENT
- 环境原因无法执行 → BLOCKED 并记录替代取证；H5/人工类不适用（纯后端 Feature，无 UNKNOWN 环境项预期）
