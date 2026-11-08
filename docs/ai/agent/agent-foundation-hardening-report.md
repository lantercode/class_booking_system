# Agent 接入前基础工程收口报告

- **日期**：2026-11-07
- **范围**：仅 AI Tool 平台基础工程收口（P0-1 ~ P0-5）
- **风险等级**：L4（涉及认证信任边界、租户隔离与共享中间件；无 Service / Repository / DB 结构变更）
- **结论**：具备进入火山方舟接入阶段的条件（遗留项见第 6 节）
- **未接入**：火山方舟 / DeepSeek / LangGraph / 新 MCP Server / 新业务功能

---

## 1. 修改文件清单

| # | 文件 | 类型 |
|---|------|------|
| 1 | `apps/api/src/app/ai/mcp_server.py` | 修改 |
| 2 | `apps/api/src/app/ai/agent/runtime.py` | 修改 |
| 3 | `apps/api/src/app/modules/ai/router.py` | 修改 |
| 4 | `apps/api/src/app/middleware/rate_limiter.py` | 修改 |
| 5 | `apps/api/src/app/main.py` | 修改 |
| 6 | `apps/api/src/app/core/config.py` | 修改 |
| 7 | `apps/api/tests/unit/test_ai_p1_tool_platform.py` | 修改（适配新签名） |
| 8 | `apps/api/tests/unit/test_ai_agent_handler_contract.py` | 新增 |
| 9 | `apps/api/tests/unit/test_ai_agent_hardening.py` | 新增 |
| 10 | `apps/api/tests/unit/conftest.py` | 新增（单元测试隔离） |
| 11 | `apps/api/tests/test_agent_runtime.py` | 删除（旧手动脚本） |

未改动：业务 Service、Repository、数据库结构 / Migration、6 个 Tool 的业务实现、Miniapp UI。

---

## 2. 每项修改原因与修复结果

### P0-1 测试与 Handler 漂移

**原有问题**

- `TOOL_SPECS["query_schedules"].handler_name = "query_schedules_impl"`，但旧测试 `tests/test_agent_runtime.py` 仍 monkeypatch `query_schedules`，mock 不生效，实际调用会穿透到真实 Handler / 数据库。
- 旧脚本不属于 `tests/unit`，CI 不覆盖。
- `query_schedules_impl` 空结果分支返回 `str` 而非常量类型 `ToolOutcome`，与结构化 data 契约不一致。
- `execute_tool` 使用 `globals()[spec.handler_name]`，注册表与实现漂移时抛 `KeyError`，缺少可诊断错误。

**修复结果**

- `execute_tool` 改为 `globals().get(...)` + 可调用性断言，漂移时返回 `system_error / ToolHandlerMissing` 并记录日志，不再静默或抛裸异常。
- `query_schedules_impl` 空结果统一返回 `ToolOutcome("success", 文本, data={"schedules": []})`。
- 删除旧手动脚本 `tests/test_agent_runtime.py`；新增 `tests/unit/test_ai_agent_handler_contract.py`：
  - `TOOL_SPECS` ↔ Handler ↔ `@mcp.tool` 入口三方一致性；
  - 显式断言 `execute_tool` 调用的是 `query_schedules_impl`，且不会调用 MCP 文本包装函数；
  - 空结果结构化契约；
  - Runtime 全链路 mock，不触发 `SessionLocal`。
- 新测试位于 `tests/unit`，已纳入 CI 的 `pytest tests/unit`。

### P0-2 收紧 execute_tool 信任边界

**原有问题**

- `execute_tool(tool_name, arguments, context)` 暴露 `context` 参数，任意调用方可在单次调用中传入伪造的 `ToolContext`。
- 身份链虽已有 JWT → `AgentRuntime` → `ToolContext` → ContextVar，但入口签名未强制。

**修复结果**

- `execute_tool` 签名收敛为 `(tool_name, arguments)`，**不接受 user_id / tenant_id / ToolContext**，身份只能来自 `ContextVar`。
- `AgentRuntime._call_tool` 显式 `with tool_context(ctx)` 绑定后再调用，`ctx` 仅来自 `get_current_user` 注入的构造参数。
- 新增绑定前校验：请求级 `ContextVar`（HTTP 由 `get_current_user` 写入）与 `ToolContext` 不一致时返回 `business_error / 403`，防止上层上下文被污染后静默覆盖身份；stdio 独立运行时两者为 `None`，仍由宿主显式注入。
- `_filter_arguments` 继续丢弃未声明的身份字段：模型/前端即使把 `user_id`、`tenant_id` 塞进 arguments 也不会生效。
- 原 JWT → ToolContext → ContextVar → Service 身份链未被破坏。

### P0-3 AI 接口限流

**原有问题**

- `RateLimiterMiddleware` 已实现但从未注册（`RATE_LIMIT_CONFIG` 仅定义未使用），AI 接口实际无用户级限流。

**修复结果**

- 复用现有 `RateLimiterMiddleware` 与 `RateLimiter`，新增：
  - `path_limits`：路径前缀 → `(limit, window)`；
  - `user_key_paths`：按已签名 JWT 的 `user_id` 分桶，未带 Token 时降级 IP；
  - `only_path_limits=True`：未命中配置的路径直接放行；
  - `redis_provider`：惰性复用应用级 Redis 单例，避免导入阶段连接；
  - `OPTIONS` 预检直接放行。
- `main.py` 注册中间件，仅匹配 `/api/v1/ai/chat`；默认 `20 次 / 60 秒 / 用户`（`AI_CHAT_RATE_LIMIT` / `AI_CHAT_RATE_WINDOW` 可配）。
- 429 返回统一信封：`{"code": 429, "msg": "请求过于频繁，请稍后再试", "data": {"retry_after": N}}`。
- 其他业务 API 不受影响（单测验证 5 次连续请求全部 200）。

### P0-4 session_id 参数校验

**原有问题**

- `session_id` 仅受 `str | None` 约束，可传入超长/特殊字符，直接拼入 Redis key。

**修复结果**

- 统一规则 `^[A-Za-z0-9_-]{1,64}$`，覆盖 `POST /ai/chat` body、`GET/DELETE /ai/history` query 三个入口。
- 会话归属仍由 `SessionManager` 的 `ai:session:user_{user_id}:{session_id}`、`ai:state:...`、`ai:lock:...` key 前缀保证，无法通过猜测他人的 `session_id` 读取他人历史。
- 小程序现有 `session_${userId}` 格式合法，无兼容影响。

### P0-5 补充测试

| 验收点 | 测试位置 |
|---|---|
| 不同用户 Session 隔离 | `test_ai_agent_hardening.py::test_session_history_is_isolated_between_users` |
| 不同 session_id 隔离 | `test_ai_agent_hardening.py::test_session_scoped_by_session_id` |
| 跨租户显式身份拒绝 | `test_ai_agent_hardening.py::test_explicit_identity_must_match_trusted_context` |
| 伪造 ToolContext | `test_ai_agent_hardening.py::test_execute_tool_rejects_forged_context_argument` |
| 请求上下文污染 | `test_ai_agent_hardening.py::test_execute_tool_rejects_polluted_request_context` |
| 非法 session_id | `test_ai_agent_hardening.py::test_chat_request_rejects_invalid_session_id` 等 |
| 超过限流阈值 | `test_ai_agent_hardening.py::test_rate_limit_returns_429_envelope_after_threshold` |
| 限流按用户隔离 | `test_ai_agent_hardening.py::test_rate_limit_is_per_user_not_shared` |
| query_schedules 调用真实 Handler | `test_ai_agent_handler_contract.py::test_execute_tool_uses_spec_handler` |
| Tool 业务异常正确返回 | `test_ai_p1_tool_platform.py::test_tool_business_error_is_not_success`（既有） |

新增 `tests/unit/conftest.py` 以同名 no-op fixture 覆盖父级 `tests/conftest.py` 的 Redis ping / 数据库种子 fixture，确保单元测试不写真实库。

---

## 3. 测试执行命令

```bash
# 1. 静态检查（CI 同款）
cd apps/api
uv run ruff check .
bash scripts/mypy_baseline_check.sh

# 2. 单元测试（CI 同款）
uv run pytest tests/unit --tb=short -q

# 3. 证明单元测试不依赖真实 DB / Redis（使用不可达地址）
DATABASE_URL='postgresql+asyncpg://bad:bad@127.0.0.1:1/bad' \
REDIS_URL='redis://127.0.0.1:1/0' \
uv run pytest tests/unit -q --tb=short

# 4. 集成测试（CI 同款排除项）
uv run pytest tests/integration --tb=short -q \
  --ignore=tests/integration/test_admin_user_real.py \
  --ignore=tests/integration/test_tenant_isolation.py \
  --ignore=tests/integration/test_booking_ownership.py \
  --deselect tests/integration/test_user_api.py::TestUserCRUD::test_create_user_success \
  --deselect tests/integration/test_booking_fk_membership_card.py::TestBookingFkMigrationLogic::test_migration_cleanup_clears_orphan_and_readds_fk \
  --deselect tests/integration/test_status_check_constraints.py::TestExistingDataIntact
```

---

## 4. 实际测试结果

| 项目 | 结果 |
|---|---|
| Ruff | `All checks passed!` |
| Mypy baseline ratchet | 通过（退出码 0） |
| 新增单元测试 | 30 条，全部通过 |
| 单元测试（常规环境） | **165 passed** |
| 单元测试（DB / Redis 不可达） | **165 passed**，证明不依赖真实 DB / Redis |
| 集成测试（CI 排除项之外） | **268 passed, 1 skipped, 5 deselected**（首轮，64.44s） |
| 集成测试第二轮 | 267 passed + 1 条既有 flake（见第 6 节），单条重跑通过 |

> 以上均为实际执行结果；未运行的测试（CI 明确 ignore 的 3 个文件与 5 个 deselect）未计入通过数。

---

## 5. 架构复核（Architect Review）

- 复核结论：风险等级 **L4**；`execute_tool` 已不接受身份参数，HTTP / 模型侧无法伪造身份；`tool_context` 双层绑定按 Token LIFO 复位，无泄漏；限流仅命中 `/api/v1/ai/chat`；`session_id` 三入口全覆盖。
- 复核提出的「单元测试受父级 conftest 影响」与「租户比对自证」两项中风险，已在本次修复：
  - 新增 `tests/unit/conftest.py` 覆盖 autouse DB/Redis fixture；
  - `execute_tool` 增加请求级 ContextVar 与 `ToolContext` 的一致性校验。
- 复核确认：无新增 Service / Repository / DB / MCP 入口，429 使用统一信封，未触碰权限 bypass 与租户白名单，符合 `.trae/rules`。

---

## 6. 未解决问题（不阻断本次结论）

1. **FastMCP `exclude_args` 弃用告警**：`@mcp.tool(exclude_args=...)` 在 FastMCP 新版本标记 deprecated，当前功能正常；升级时改为依赖注入。
2. **限流 Redis 降级**：首次获取 Redis 失败后本实例降级为进程内存计数，多实例计数不共享；生产 Redis 不可达时应用本身会在 `lifespan` 启动失败，因此仅影响降级窗口。
3. **429 与 CORS 顺序**：限流中间件位于最外层，早于 CORS；当前 Web 三端同源、小程序无 CORS，无实际影响；若未来跨域直连 AI 接口需调整顺序。
4. **Handler 四关靠实现约定**：`execute_tool` 不直接执行 `_gate`，由各 Handler 首行调用。当前 6 个 Tool 均已调用；建议后续接入批次补结构性契约测试，防止新增 Tool 漏写。
5. **`_gate` 租户比对冗余**：`get_tenant_id() != ctx.tenant_id` 在 `tool_context` 内为恒假，真正校验依赖 `is_user_in_tenant` 与本次新增的绑定前比对；可在后续清理。
6. **既有测试 flake**：`tests/integration/test_booking_reschedule.py::test_b2_count_card_cross_card_reschedule` 偶发因同秒事务排序失败（本次未改动 booking / membership，单条重跑通过），属存量问题。
7. **根目录其他手动脚本**：`tests/test_mcp_server.py`、`tests/test_multi_turn_booking.py` 等仍不在 CI 且可能访问真实库，本次未处理。
8. **session_id 契约收紧**：由 `str | None` 改为 `str`，外部客户端若显式传 `null` 将返回 422；需在后续接入文档中注明。

---

## 7. 是否具备进入火山方舟接入阶段的条件

**具备（有条件）。**

已满足：

- Tool 执行入口不再接受身份参数，身份链固定为 JWT → AgentRuntime → ToolContext → ContextVar → Service；
- 测试与 Handler 一致，且单元测试可在无 DB / Redis 环境运行；
- `/api/v1/ai/chat` 已具备用户级限流与统一 429 信封；
- `session_id` 长度 / 字符集 / 用户归属三重约束；
- 全量单测、CI 集成测试、Ruff、Mypy baseline 均通过。

进入接入阶段时必须保持：

1. LLM 只产出意图与业务参数，**不得产出或覆盖 user_id / tenant_id**；
2. 所有 Tool 调用仍必须经过 `execute_tool` 与 `ToolContext`，禁止绕过；
3. 写操作继续保留用户确认环节与 Service 层事务；
4. 为 LLM 调用补充超时 / 重试预算后再上线，限流参数按实际成本复核。
