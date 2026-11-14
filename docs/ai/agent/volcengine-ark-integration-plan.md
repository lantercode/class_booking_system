# 火山方舟（Volcengine Ark）LLM 最小可行接入实施方案

- **文档性质**：只读代码检查 + 方案设计；本轮未修改任何源代码、配置、测试、迁移或数据库。
- **风险等级**：L4（涉及外部模型依赖、认证/租户信任边界、成本与限流；不改核心业务状态机）。
- **适用阶段**：Agent 基础工程收口之后、写操作开放之前。
- **第一阶段范围**：只开放只读 Tool（`query_courses`、`query_schedules`、`get_my_bookings`、`get_my_balance`）；`create_booking`、`cancel_booking` 不进入模型可见工具集。
- **不引入**：LangGraph、MCP Client、外部 MCP transport、流式 SSE、RAG 真实向量库、新业务 Tool。

---

## 1. 当前架构分析

### 1.1 真实调用链路（已核对代码）

```
客户端（小程序 AiChatPanel）
  → POST /api/v1/ai/chat（JWT + x-tenant-slug）
  → TenantASGIMiddleware（写租户 ContextVar）
  → get_current_user（JWT → user_id/tenant_id/role_id 覆盖 ContextVar）
  → modules/ai/router.py::chat
  → AgentRuntime.chat
      → SessionManager（Redis 历史/状态/锁）
      → IntentRecognizer（关键词规则）
      → AgentRuntime._execute_intent（if/elif 分发）
      → AgentRuntime._call_tool
          → tool_context(ToolContext) 绑定 ContextVar
          → execute_tool(tool_name, arguments)
              → _filter_arguments（丢弃未声明参数）
              → Handler → _gate 四关
                  Authentication → Authorization → Tenant Validation → Input Validation
              → Service → Repository → PostgreSQL
```

关键代码位置：

- 路由入口：[router.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/ai/router.py#L51-L85)（`get_agent_runtime`、`chat`）。
- Runtime 主流程：[runtime.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/agent/runtime.py#L86-L181)（`AgentRuntime.chat`）。
- 身份注入：[runtime.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/agent/runtime.py#L232-L274)（`_tool_context`、`_call_tool`）。
- Tool 统一入口：[mcp_server.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/mcp_server.py#L666-L762)（`execute_tool`）。
- 四关校验：[mcp_server.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/mcp_server.py#L196-L250)（`_authorize`、`_gate`）。
- 会话存储：[session.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/agent/session.py#L39-L152)。
- 规则意图：[intent.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/agent/intent.py#L25-L127)。
- Prompt 组装：[prompts.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/agent/prompts.py#L13-L82)。

### 1.2 现状事实（必须作为方案前提）

1. **Runtime 当前完全没有 LLM 调用**：`AgentRuntime.chat` 走 `IntentRecognizer` + `if/elif` 规则分发；`system_messages` 每请求组装，但只记录长度/指纹，不发送给模型（[runtime.py:L100-L102](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/agent/runtime.py#L100-L102)、[prompts.py:L5-L9](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/agent/prompts.py#L5-L9)）。
2. **全仓没有可用的 LLM SDK/HTTP 调用点**：`pyproject.toml` 无 `volcengine` / `openai` / `langchain` 依赖；`ai/rag/embedder.py` 的 OpenAI 调用仍是注释 stub；`ai/rag/retriever.py` 为硬编码 stub，按规则不得作为数据源。
3. **`TOOL_SPECS` 是 Tool 元数据单一事实源，但不含 JSON Schema/描述**：结构为 `name / handler_name / required_roles / is_write / input_fields`（[mcp_server.py:L149-L180](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/mcp_server.py#L149-L180)）。Tool 的参数类型、描述目前只存在于函数签名与 docstring，由 FastMCP 反射生成；没有一个可直接给 LLM 的 schema 导出函数。
4. **没有“按角色过滤后的工具清单”**：角色判断只在执行期由 `_authorize` 完成（`get_user_role_codes` ∩ `spec.required_roles`，[mcp_server.py:L196-L209](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/mcp_server.py#L196-L209)）。LLM 需要“先拿到可用工具列表”，当前不存在该能力；不能把 `role_id` 当成角色码使用。
5. **Tool 返回以自然语言文本为主**：只有 `query_schedules` 额外返回结构化 `ToolOutcome.data`（[mcp_server.py:L391-L462](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/mcp_server.py#L391-L462)）；其余 Tool 只返回文本。接 LLM 时文本可直接作为 tool message，但必须裁剪与加状态标注。
6. **已有用户级 AI 限流**：`/api/v1/ai/chat` 默认 20 次 / 60 秒 / 用户（[config.py:L45-L47](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/config.py#L45-L47)、[main.py:L208-L222](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/main.py#L208-L222)）。LLM 的成本风险仍需循环次数、输出 token、超时预算等应用内约束。
7. **会话三把 Redis key**：历史 1 小时、最多 20 条消息；中间状态 10 分钟；并发锁 5 秒（[session.py:L33-L57](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/agent/session.py#L33-L57)、[runtime.py:L632-L678](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/agent/runtime.py#L632-L678)）。**5 秒锁 TTL 小于 LLM 请求预期耗时，是接入前必须调整的点**，否则同一会话的并发请求可能在第一个请求尚未结束时进入。
8. **`/ai/chat` 契约**：一次性 JSON，`data.response` 为最终文本；无 SSE、无工具 trace（[router.py:L63-L85](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/ai/router.py#L63-L85)）。`ChatResponse.data` 是 `dict`，新增可选键不会改变 OpenAPI 结构，但仍需按契约规则评估消费端。
9. **现有测试已覆盖 Tool 契约与信任边界**：`test_ai_agent_handler_contract.py`、`test_ai_agent_hardening.py`、`test_ai_p1_tool_platform.py` 均不依赖真实 DB/Redis/网络，可作为 LLM 接入的回归基线。
10. **当前没有安装方舟 SDK**：`pyproject.toml` 的运行时依赖中没有 `volcengine-python-sdk`；`httpx` 仅出现在 dev 依赖中，但同时是 `fastmcp` client extra 的传递依赖（`uv.lock` 中 `fastmcp-slim[client] → httpx`），运行时可用但不建议依赖传递依赖。

### 1.3 现有 LLM 缺失点

| 缺失项 | 现状 | 影响 |
|---|---|---|
| LLM Provider | 无 | 无法进行语义理解与 function calling |
| Tool Schema 导出 | 只有 FastMCP 反射，无 `TOOL_SPECS → tools[]` 转换 | 无法把工具清单交给模型 |
| 角色过滤工具清单 | 无 | 模型可能看到并尝试调用其角色不可用的 Tool |
| Agent Loop | 无（仅两轮状态机） | 无法处理“模型请求工具 → 读取结果 → 继续回答” |
| LLM 参数校验 | 无 | 模型输出的 JSON 参数不可信，必须校验后再进 Tool |
| 超时/重试/预算 | 无 | 外部依赖故障会拖垮请求，成本不可控 |
| Tool 结果裁剪 | 无 | 工具文本可能过长，撑大 prompt |
| 请求级 trace | 有基础 trace，但无 `request_id` / 模式 / 模型调用次数 | 线上排障与灰度观测不足 |
| 只读工具闸门 | 无 | 规则回退仍可能执行写操作 |
| 锁 TTL 匹配 LLM 耗时 | 5 秒 | 并发请求可能绕过多轮会话互斥 |

### 1.4 保留 / 扩展 / 新增

| 类型 | 模块/文件 | 处理方式 | 说明 |
|---|---|---|---|
| 保留 | `ai/mcp_server.py` 的 `TOOL_SPECS`、`execute_tool`、`_gate`、6 个 Handler、`ToolOutcome`、`tool_context` | 不改业务实现 | Tool 调用必须继续经 `execute_tool()` |
| 保留 | `ai/agent/session.py::SessionManager` | 不新增存储 | 继续使用 `ai:session/state/lock:{user}:{session}` 三层 key |
| 保留 | `ai/agent/intent.py::IntentRecognizer` | 保留为规则回退 | LLM 不可用/未灰度时零回归 |
| 保留 | `modules/ai/router.py` | Phase 1 不改 | Router 不 import 任何模型 SDK |
| 保留 | Service / Repository / 数据库结构 / Migration | 完全不动 | 业务规则仍只在 Service |
| 扩展 | `ai/mcp_server.py::ToolSpec` | 增加 `description`、`parameters`（JSON Schema） | 保持 `TOOL_SPECS` 为唯一事实源 |
| 扩展 | `ai/mcp_server.py` | 新增 `list_tool_definitions(ctx)`、`tool_specs_for_roles(...)` | 复用 `get_user_role_codes`，不造新权限体系 |
| 扩展 | `ai/agent/runtime.py` | 增加 LLM 分支、Provider 注入、锁 TTL、trace 字段、只读闸门 | 规则链路原样保留作为 fallback |
| 扩展 | `ai/agent/prompts.py` | 新增 LLM messages 构造；默认不发送明文 user_id/tenant_id；声明工具输出仅为数据 | 安全加固 |
| 扩展 | `core/config.py` | 增加 `AI_LLM_*` / `ARK_API_KEY` 配置与启动校验 | 密钥只来自环境变量 |
| 扩展 | `pyproject.toml` | 显式声明 `httpx>=0.27` | 避免依赖 fastmcp 传递依赖 |
| 扩展 | `.env.example` / `.env.prod.example` | 增加占位配置说明 | 不写真实密钥 |
| 新增 | `apps/api/src/app/ai/llm/base.py` | Provider 协议、消息/响应/异常类型 | 与 Runtime 解耦 |
| 新增 | `apps/api/src/app/ai/llm/ark.py` | 方舟 OpenAI 兼容 HTTP Provider | 唯一 SDK/HTTP 调用位置 |
| 新增 | `apps/api/src/app/ai/llm/factory.py` | 单例创建/关闭 Provider | 便于 mock 与生命周期管理 |
| 新增 | `apps/api/src/app/ai/agent/tool_schema.py` | `TOOL_SPECS → OpenAI/方舟 tools[]` 转换与校验 | 纯函数，可离线单测 |
| 新增 | `apps/api/src/app/ai/agent/loop.py` | Function calling 执行循环 | 不放进 Router/Runtime 主体 |
| 新增 | `apps/api/tests/unit/test_ai_llm_*.py` | Provider/Schema/Loop/Security/Config 测试 | 全部 mock，无网络/DB |

### 1.5 UNKNOWN 与已确认项

**已确认（2026-11-09，详见附录 B）**

- 数据面 Base URL：`https://ark.cn-beijing.volces.com/api/v3`，OpenAI 兼容 Chat API。
- 推荐模型均支持 `tools`（Function Calling）与多 `tool_calls`；`tool_choice` 自 `doubao-seed-1-6` 系列起支持。
- 可直接用模型 ID（如 `doubao-seed-2-1-lite-260915`）作为 `model`，也兼容推理接入点 `ep-xxx`。
- 生产出网只需放行域名 `ark.cn-beijing.volces.com:443`。

**仍为 UNKNOWN**

| # | UNKNOWN | 影响 | 处理方式 |
|---|---|---|---|
| U1 | 方舟账号是否已开通目标模型、账号实际 RPM/TPM | 默认 `AI_LLM_MODEL` 与容量规划 | Phase 0 在控制台「开通管理」核对；默认值可配置 |
| U2 | 方舟响应 `usage` 字段是否始终存在 | 成本统计可能缺失 | 按可选字段处理，缺失时记 0/unknown |
| U3 | `fastmcp 3.4.7` 的 schema 反射 API（`mcp.list_tools()` 是否 async、返回结构） | 只影响 drift 测试，不影响运行时 | 运行时不依赖反射；drift 测试在 Phase 0 确认后再加 |
| U4 | 部署环境是否强制 HTTPS 代理 | Provider 不可达 | Provider 由 `httpx` 实现，默认读取 `HTTPS_PROXY` 等环境变量 |
| U5 | `thinking` 深度思考关闭后的实际首 token 延迟 | 影响 15s 预算 | Phase 0 真实契约冒烟测量 |

---

## 2. 目标架构图

```mermaid
flowchart TD
    C["客户端（小程序 / Web）"] -->|"POST /api/v1/ai/chat\nJWT + x-tenant-slug"| R["modules/ai/router.py::chat"]
    R --> RT["AgentRuntime.chat"]

    RT -->|"AI_LLM_ENABLED=false\n或租户未灰度"| RULE["规则链路（保留）\nIntentRecognizer → _execute_intent"]
    RT -->|"启用"| MODE{"Provider 可用?\n预算内?"}

    MODE -->|"否 / 异常"| RULE
    MODE -->|"是"| PRE["取可信 ToolContext\n（JWT → Runtime，唯一来源）"]

    PRE --> DEF["mcp_server.list_tool_definitions(ctx)\n复用 get_user_role_codes + required_roles\n只读过滤：is_write=False"]
    DEF --> TS["agent/tool_schema.py\nTOOL_SPECS → OpenAI/方舟 tools[]"]
    TS --> LOOP["agent/loop.py\nAgentLoop（最大循环 + 总预算）"]

    LOOP --> PROMPT["prompts.build_llm_messages\nsystem + 最近历史 + 当前输入"]
    LOOP -->|"HTTPS POST /chat/completions"| ARK["llm/ark.py::ArkProvider"]
    ARK --> ARKAPI[("火山方舟 API")]
    LOOP -->|"tool_calls 参数校验/去重"| EX["execute_tool(name, args)\n四关 + 错误封套"]
    EX --> T["Tool Handler（原有 6 个）"]
    T --> S["Service 层（业务规则唯一权威）"]
    S --> RP["Repository（TenantAware）"]
    RP --> DB[("PostgreSQL")]

    RT --> SM["SessionManager\nRedis 历史/状态/锁"]
    LOOP -->|"最终文本 / 兜底文本"| RT
    RT -->|"data.response"| R
    R -->|"统一 JSON 信封"| C

    RULE --> EX
```

说明：

- Router 只依赖 `AgentRuntime`，不 import `ai/llm/*`、不 import `httpx`、不拼接方舟请求。
- Provider 是唯一外部 HTTP 调用点；Runtime 只依赖 `LLMProvider` 协议。
- Tool 只经 `execute_tool()` 执行；LLM 产出的 `tool_calls.name/arguments` 只是“意图输入”，不是身份或权限来源。

---

## 3. 模块职责与设计细节

### 3.1 新增 Provider 适配层

**位置**：`apps/api/src/app/ai/llm/`，不在 `router.py`，也不在 `runtime.py` 内直接调用 SDK。

| 文件 | 职责 |
|---|---|
| `ai/llm/base.py` | 定义 `LLMProvider` 协议、`LLMMessage`、`LLMToolCall`、`LLMResponse`、统一异常族 |
| `ai/llm/ark.py` | `ArkProvider`：方舟 OpenAI 兼容 `/chat/completions` 调用、状态码映射、重试策略、JSON 解析 |
| `ai/llm/factory.py` | `get_llm_provider()` 单例、`close_llm_provider()`（可在 `main.py` lifespan 关闭） |
| `ai/llm/__init__.py` | 只导出协议与工厂，不暴露密钥 |

建议接口（示意）：

```python
class LLMProvider(Protocol):
    name: str

    async def chat(
        self,
        *,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
    ) -> LLMResponse: ...
```

```python
@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: str   # 原始 JSON 字符串，未解析

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[LLMToolCall]
    finish_reason: str | None
    usage: dict | None
```

异常族（全部映射为 AI 层错误，禁止把上游原文透传给用户）：

- `LLMTimeoutError`
- `LLMAuthError`（401/403）
- `LLMRateLimitError`（429，携带 `retry_after`）
- `LLMUpstreamError`（5xx）
- `LLMBadRequestError`（400/422）
- `LLMResponseFormatError`（响应非法/JSON 解析失败）

### 3.2 方舟 API 调用细节（OpenAI 兼容）

> 方舟同时提供官方 SDK 与 OpenAI 兼容 HTTP。本方案**优先直接 HTTPS**，避免引入 SDK 版本与额外依赖；SDK 仅作为 U6 的备选。

| 项 | 建议值 |
|---|---|
| Base URL | `https://ark.cn-beijing.volces.com/api/v3`（可配置） |
| Endpoint | `POST {base_url}/chat/completions` |
| Auth | `Authorization: Bearer {ARK_API_KEY}` |
| Header | `Content-Type: application/json` |
| 请求字段 | `model`、`messages`、`tools`、`tool_choice="auto"`、`temperature`、`max_tokens`、`stream=false` |
| 模型标识 | `AI_LLM_MODEL` 必填；可为 Endpoint ID 或模型名，具体以控制台为准（U1） |
| 响应 | `choices[0].message.content`、`choices[0].message.tool_calls[]`、`choices[0].finish_reason`、`usage` |
| tool_call 结构 | `{ "id": "...", "type": "function", "function": { "name": "...", "arguments": "{json字符串}" } }` |
| 后续消息 | assistant 消息回填 `tool_calls`；每个工具结果以 `{"role":"tool","tool_call_id":id,"content":"..."}` 追加 |
| 流式 | **关闭**；本轮不引入 SSE |
| 并行工具调用 | 不显式开启；若模型返回多个，按顺序执行且每轮最多 2 个（U3） |

请求体示例：

```json
{
  "model": "ep-xxxxxxxx",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "明天有什么瑜伽课"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "query_schedules",
        "description": "查询指定日期范围内的排期",
        "parameters": {
          "type": "object",
          "properties": {
            "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "keyword": {"type": "string", "maxLength": 50},
            "days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7}
          },
          "additionalProperties": false
        }
      }
    }
  ],
  "tool_choice": "auto",
  "temperature": 0.2,
  "max_tokens": 800,
  "stream": false
}
```

### 3.3 配置项与密钥管理

**原则**：

- 密钥只来自环境变量 / `.env.*`；`.env`、`.env.prod`、`.env.production` 已在 gitignore 中；`.env.example` 只放占位符。
- `ARK_API_KEY` 使用 `Field(default="", repr=False)`，任何日志、异常、响应、模型消息都不得包含它。
- 配置校验放在 `Settings.model_validator`（与现有 `validate_storage_backend` 同一模式），启动即失败，不允许“静默降级为无密钥运行”。
- 模型名必填，不设默认值，避免误用错误模型/计费主体。
- 生产环境启用 LLM 时必须显式配置租户白名单，避免“全局开关一开全量生效”。

| 配置项 | 默认值 | 说明 / 校验 |
|---|---|---|
| `AI_LLM_ENABLED` | `false` | 总开关；默认关闭，零回归 |
| `AI_LLM_PROVIDER` | `"ark"` | 当前仅 `ark` |
| `AI_LLM_MODEL` | `""` | 启用时必填；Endpoint ID 或模型名（U1） |
| `AI_LLM_BASE_URL` | `"https://ark.cn-beijing.volces.com/api/v3"` | 启用时必须 `https://` |
| `ARK_API_KEY` | `""` | 启用时必填；机密，禁止日志/repr |
| `AI_LLM_CONNECT_TIMEOUT_SECONDS` | `3` | 1–10 |
| `AI_LLM_TIMEOUT_SECONDS` | `6` | 单次模型调用读超时；1–30 |
| `AI_LLM_MAX_RETRIES` | `2` | 最多重试次数（总尝试 = 1 + retries）；0–3 |
| `AI_LLM_RETRY_BASE_MS` | `300` | 指数退避基数：300、900；上限 2s |
| `AI_LLM_MAX_TOOL_LOOPS` | `4` | 最大模型调用轮次；1–6；Phase 1 建议设 `2` |
| `AI_LLM_TOTAL_BUDGET_MS` | `15000` | 单次 `/ai/chat` LLM 总预算；5000–60000 |
| `AI_LLM_TOOL_TIMEOUT_SECONDS` | `4` | 单次只读 Tool 超时；1–15 |
| `AI_LLM_MAX_OUTPUT_TOKENS` | `800` | 100–4096 |
| `AI_LLM_TEMPERATURE` | `0.2` | 0–1 |
| `AI_LLM_HISTORY_MESSAGES` | `6` | 最多 6 条（3 轮） |
| `AI_LLM_HISTORY_MESSAGE_MAX_CHARS` | `500` | 单条历史裁剪 |
| `AI_LLM_TOOL_RESULT_MAX_CHARS` | `4000` | 单条 tool message 裁剪 |
| `AI_LLM_READONLY_ONLY` | `true` | Phase 1 必须为 true；写工具不进入 tools[]，规则回退也拦截写意图 |
| `AI_LLM_ENABLED_TENANTS` | `""` | 逗号分隔 tenant_id；生产启用时必须非空（灰度白名单） |
| `AI_EXPOSE_TOOL_TRACE` | `false` | Phase 3 可选：是否在响应中返回 `tool_trace` |
| `AI_CHAT_RATE_LIMIT` / `AI_CHAT_RATE_WINDOW` | `20` / `60` | 复用现有中间件；接入后按成本复核 |

配置校验伪代码：

```python
@model_validator(mode="after")
def validate_llm(self):
    if not self.AI_LLM_ENABLED:
        return self
    if self.AI_LLM_PROVIDER != "ark":
        raise ValueError("AI_LLM_PROVIDER 当前仅支持 ark")
    if not self.AI_LLM_MODEL:
        raise ValueError("启用 AI_LLM 时 AI_LLM_MODEL 必填")
    if not self.ARK_API_KEY:
        raise ValueError("启用 AI_LLM 时 ARK_API_KEY 必填（仅环境变量）")
    if not self.AI_LLM_BASE_URL.startswith("https://"):
        raise ValueError("AI_LLM_BASE_URL 必须为 https://")
    if self.is_production and not self.AI_LLM_ENABLED_TENANTS.strip():
        raise ValueError("生产环境启用 AI_LLM 必须配置 AI_LLM_ENABLED_TENANTS 白名单")
    # 其余数值范围校验略
    return self
```

### 3.4 Tool Schema 转换（单一来源 `TOOL_SPECS`）

**设计决定**：`TOOL_SPECS` 继续作为唯一注册表；不新建第二套工具清单，也不把 FastMCP 反射结果作为运行时 schema 源。

扩展 `ToolSpec`（仅增加元数据字段，不改任何 Handler）：

```python
@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    handler_name: str
    required_roles: frozenset[str]
    is_write: bool
    input_fields: frozenset[str]
    description: str
    parameters: dict[str, Any]   # JSON Schema，properties 必须与 input_fields 一致
```

新增纯函数（建议放在 `ai/agent/tool_schema.py`）：

- `build_openai_tools(names: Iterable[str]) -> list[dict]`：从 `TOOL_SPECS` 取 `description/parameters`，包装成 `{"type":"function","function":{...}}`。
- `validate_tool_specs() -> None`：断言 `parameters.properties` 的键集合 == `input_fields`，且不含 `user_id/tenant_id`。
- `allowed_tool_names(role_codes: set[str], readonly_only: bool) -> set[str]`：`spec.required_roles ∩ role_codes`，再按 `is_write` 过滤。

新增异步函数（放在 `ai/mcp_server.py`，因为它拥有 `TOOL_SPECS` 与 `SessionLocal`）：

```python
async def list_tool_definitions(ctx: ToolContext, *, readonly_only: bool = True) -> list[dict]:
    async with SessionLocal() as db:
        roles = await get_user_role_codes(db, user_id=ctx.user_id, tenant_id=ctx.tenant_id)
    allowed = allowed_tool_names(roles, readonly_only=readonly_only)
    return build_openai_tools(allowed)
```

要点：

- 角色查询**复用** `core/rbac/checker.py::get_user_role_codes`（与 `_authorize` 同一个函数）；查询异常返回空集合（fail closed），结果为空时 LLM 不获得任何工具，只能做通用回答或走规则回退。
- 不使用 JWT 里的 `role_id` 做工具过滤（`role_id` 是单个角色 ID，不是角色码集合）。
- 执行期仍由 `_authorize` 二次校验；列表过滤只是“告诉模型能做什么”，不是授权替代。
- 不新增 `list_tools_for_role` HTTP 端点，避免扩大攻击面。

第一阶段各角色可见工具：

| 角色 | 可见只读 Tool | 数量 |
|---|---|---|
| `student` | `query_courses`、`query_schedules`、`get_my_bookings`、`get_my_balance` | 4 |
| `teacher` / `admin` / `super_admin` | `query_courses`、`query_schedules`、`get_my_bookings`（仍 `self_only`） | 3 |
| 其他/无角色 | 空集合 | 0 |

各 Tool 的 JSON Schema（与现有校验一致）：

| Tool | parameters 摘要 |
|---|---|
| `query_courses` | `keyword: string ≤50`；`category: enum[yoga,dance,fitness,kids,other]`；`level: enum[beginner,intermediate,advanced]`；`additionalProperties=false` |
| `query_schedules` | `date: string pattern YYYY-MM-DD`；`keyword: string ≤50`；`days: integer 1–30 default 7`；`additionalProperties=false` |
| `get_my_bookings` | `status: enum[booked,cancelled,checked_in,completed,no_show]`；`additionalProperties=false` |
| `get_my_balance` | `{"type":"object","properties":{},"additionalProperties":false}` |

> `create_booking` / `cancel_booking` 的 schema 可在 Phase 0 一并补齐，但 Phase 1 的 `readonly_only=True` 会将其从 tools[] 中排除。

### 3.5 Tool 参数校验（LLM 参数不可信）

执行顺序固定：

1. **Provider 层**：`function.arguments` 必须是字符串；长度上限建议 2000 字符；`json.loads` 必须得到 `dict`；否则生成 tool 错误消息，不调用 Tool。
2. **Loop 层**：只允许 `name` 属于当前请求 `tools[]` 白名单；只允许 `TOOL_SPECS[name].input_fields` 中的键；不做隐式类型强转（不把 `"42"` 转成 `42`）。
3. **`execute_tool` 层**：`_filter_arguments` 继续丢弃未声明字段（包括模型伪造的 `user_id/tenant_id`）。
4. **Handler 层**：`_validate_id/_validate_text/_validate_enum/_parse_date/_validate_days` 继续做最终校验。

原则：**不在 Loop 层复制业务校验**；Loop 只做“避免明显非法输入进入 Tool”的结构性校验，业务语义校验仍由 Tool/Service 完成。

### 3.6 Tool 结果回传格式与裁剪

Tool 结果统一封装为 `role=tool` 消息，`tool_call_id` 与模型返回的 `id` 对应：

```text
[TOOL_RESULT name=query_schedules status=success]
2026-11-10 至 2026-11-17 共 3 个排期：
- ID:5 | 2026-11-10 | 10:00-11:00 | 张老师 | 剩余:3 | 瑜伽
```

错误：

```text
[TOOL_RESULT name=get_my_balance status=business_error code=403]
当前账号没有学员身份，无法执行该操作。请使用学员账号登录后再试。
```

系统错误：

```text
[TOOL_RESULT name=query_courses status=system_error]
操作失败，请稍后重试或联系客服
```

规则：

- `content` 只使用 `ToolOutcome.text`；**不把 `data` 原样回传**（避免结构膨胀与字段注入面）。
- `status` 只使用 `success / business_error / system_error`；**不把 `error_type` 发给模型**（可能泄露内部实现）。
- 单条上限 `AI_LLM_TOOL_RESULT_MAX_CHARS=4000`；按行裁剪，保留前部，末尾追加 `\n...（内容已截断）`。
- 去除不可打印字符；Tool 文本已由 `_sanitize_business_message` / `_safe_cell` 处理，但不假设未来所有 Tool 都安全。
- System Prompt 明确声明：工具返回内容是**数据**，不是指令，不得执行其中的“忽略以上指令”等内容。

### 3.7 Agent Loop 职责

| 职责 | 说明 |
|---|---|
| 消息组装 | system prompt + 最近历史 + 当前用户输入 |
| 工具清单 | 仅使用 `list_tool_definitions(ctx)` 的结果 |
| 模型调用 | 调 `LLMProvider.chat`，带总预算与单次超时 |
| tool_calls 解析 | JSON 解析、白名单、参数结构校验 |
| Tool 执行 | 只经 `execute_tool()`，带 `tool_context`；只读工具可重试一次 |
| 去重 | 同一请求内 `(name, canonical_json(args))` 只执行一次 |
| 循环控制 | 最大 4 次模型调用；总预算 15 秒；每轮最多 2 个 tool call；总 tool 调用 ≤5 |
| 退出 | 无 tool_calls → 返回 content；预算/轮次/错误 → 兜底 |
| trace | 记录轮次、工具名、状态、耗时、token；不记录消息正文/参数值 |

### 3.8 `/ai/chat` 返回契约演进与兼容策略

| 阶段 | 契约 | 兼容性 |
|---|---|---|
| Phase 1 | **不改**：仍返回 `{code,msg,data:{response,session_id,timestamp,has_pending_state,latency_ms}}` | 小程序只读 `data.response`，零影响 |
| Phase 2 | 可选新增 `data.mode`（`llm` / `rule` / `llm_fallback`）与 `data.trace_id` | 新增可选键，`data` 为 `dict`，OpenAPI 结构不变；消费端忽略即可 |
| Phase 3 | 可选新增 `data.tool_trace`（仅 `name/status/latency_ms`），受 `AI_EXPOSE_TOOL_TRACE` 控制，默认关闭 | 不返回参数、结果、模型原文、系统提示词；不引入 SSE |
| 不实施 | SSE / WebSocket / 流式字段 | 需独立契约评审与 4 端影响面确认 |

明确禁止出现在响应中的内容：

- 模型原始 prompt / system prompt；
- 工具原始参数、`error_type`、SQL、堆栈、内部主机名；
- `ARK_API_KEY`、上游响应原文。

---

## 4. 时序图与执行循环

### 4.1 时序图

```mermaid
sequenceDiagram
    autonumber
    participant C as 客户端
    participant R as Router /api/v1/ai/chat
    participant RT as AgentRuntime
    participant SM as SessionManager
    participant M as mcp_server
    participant TS as tool_schema
    participant L as AgentLoop
    participant P as ArkProvider
    participant A as 火山方舟
    participant X as execute_tool
    participant S as Tool→Service

    C->>R: POST {message, session_id} + JWT + tenant 头
    R->>RT: AgentRuntime.chat(user_input, session_id)
    RT->>SM: get_state / get_history（key 带 user_id）
    RT->>RT: 从 JWT 构造 ToolContext（唯一身份来源）

    alt AI_LLM 未启用 / 租户未灰度 / Provider 异常
        RT->>RT: 规则链路 fallback（只读闸门拦截写意图）
        RT-->>R: 文本
    else AI_LLM 启用且预算可用
        RT->>M: list_tool_definitions(ctx, readonly_only=True)
        M->>M: get_user_role_codes ∩ required_roles
        M-->>RT: 角色过滤后的 Tool 定义
        RT->>TS: build_openai_tools(names)
        TS-->>RT: tools[]
        RT->>L: run(messages, tools, deadline)
        loop 最多 4 次模型调用 / 总预算 15s
            L->>P: chat(messages, tools, timeout)
            P->>A: POST /chat/completions
            A-->>P: message(content | tool_calls)
            P-->>L: LLMResponse
            alt 无 tool_calls
                L-->>RT: 最终文本
            else 有 tool_calls
                L->>L: JSON 解析 + 白名单 + 去重
                L->>X: execute_tool(name, args)
                X->>S: _gate → Service → Repository
                S-->>X: 业务结果/异常
                X-->>L: ToolOutcome
                L->>L: 生成 role=tool 消息（裁剪）
            end
        end
        RT->>SM: add_message(user / assistant)
        RT-->>R: 文本 + trace
    end
    R-->>C: 统一 JSON 信封
```

### 4.2 执行循环伪代码

```python
async def _chat_with_llm(self, user_input: str, session_id: str, trace: dict) -> str:
    ctx = self._tool_context()                  # 只来自 JWT，缺失则直接 401 文案
    if ctx is None:
        return "请先登录后再使用该功能"

    deadline = time.monotonic() + settings.AI_LLM_TOTAL_BUDGET_MS / 1000
    definitions = await list_tool_definitions(ctx, readonly_only=settings.AI_LLM_READONLY_ONLY)
    tool_names = {d["function"]["name"] for d in definitions}
    messages = build_llm_messages(
        system_messages=self.build_system_messages(),
        history=await self.session.get_history(session_id),
        user_input=user_input,
    )

    cache: dict[tuple[str, str], ToolOutcome] = {}
    llm_calls = 0
    tool_calls = 0
    last_success_text: str | None = None

    try:
        while llm_calls < settings.AI_LLM_MAX_TOOL_LOOPS:
            if time.monotonic() >= deadline:
                return _timeout_reply(last_success_text)

            response = await call_with_retry(
                provider.chat(
                    messages=messages,
                    tools=definitions,
                    temperature=settings.AI_LLM_TEMPERATURE,
                    max_tokens=settings.AI_LLM_MAX_OUTPUT_TOKENS,
                    timeout_s=settings.AI_LLM_TIMEOUT_SECONDS,
                ),
                deadline=deadline,
            )
            llm_calls += 1
            trace["llm_calls"] = llm_calls

            if not response.tool_calls:
                return response.content or _empty_reply()

            messages.append(_assistant_tool_call_message(response))

            for call in response.tool_calls[:2]:
                if tool_calls >= 5:
                    break
                if call.name not in tool_names:
                    messages.append(_tool_error(call.id, call.name, "TOOL_NOT_ALLOWED"))
                    continue

                args = parse_json_object(call.arguments)
                if args is None or not _args_structurally_valid(call.name, args):
                    messages.append(_tool_error(call.id, call.name, "INVALID_ARGUMENTS"))
                    continue

                key = (call.name, canonical_json(args))
                if key in cache:
                    messages.append(_tool_message(call.id, cache[key], duplicated=True))
                    continue

                outcome = await execute_tool_with_timeout(
                    call.name, args, timeout=settings.AI_LLM_TOOL_TIMEOUT_SECONDS
                )
                # 只读工具：仅对 system_error 且瞬时错误重试 1 次；写工具永不重试
                if _is_transient(outcome) and not TOOL_SPECS[call.name].is_write:
                    outcome = await execute_tool_with_timeout(call.name, args, ...)

                cache[key] = outcome
                tool_calls += 1
                trace["tools"].append({"name": call.name, "status": outcome.kind})
                if outcome.ok:
                    last_success_text = outcome.text
                messages.append(_tool_message(call.id, outcome))

                if tool_calls >= 5:
                    break

            if tool_calls >= 5:
                return _max_loop_reply(last_success_text)

        # 达到最大轮次仍有 tool_calls：不无限循环
        return _max_loop_reply(last_success_text)

    except LLMRateLimitError:
        trace["fallback_reason"] = "rate_limit"
        return await self._legacy_chat_guarded(user_input, session_id, trace)
    except LLMAuthError:
        trace["fallback_reason"] = "auth"
        return await self._legacy_chat_guarded(user_input, session_id, trace)
    except (LLMTimeoutError, LLMUpstreamError, LLMResponseFormatError):
        trace["fallback_reason"] = "provider_error"
        return await self._legacy_chat_guarded(user_input, session_id, trace)
```

### 4.3 循环与退出策略

| 项 | 建议值 | 理由 |
|---|---|---|
| 最大模型调用次数 | `4`（Phase 1 设 `2`） | 只读场景通常 1–2 次工具往返；4 次足以覆盖“查课程→查排期→回答”，同时避免成本/延迟失控 |
| 每轮最多 tool_calls | `2` | 避免一次模型输出触发过多查询；写操作未来也必须一次一个 |
| 单请求最多 Tool 调用 | `5` | 与 4 次模型调用匹配，留下 1 次冗余 |
| 单次模型超时 | `6s` | 覆盖方舟常规响应；超时即退出，不无限等待 |
| 单次 Tool 超时 | `4s` | 读查询应在此范围；超时返回 system_error |
| 总预算 | `15s` | 含所有模型调用与工具执行；超过即兜底 |
| 并发锁 TTL | `20s`（总预算 + 5s 余量） | 现有 5s 小于 LLM 耗时，必须延长；或实现续租（建议直接延长） |
| 重复调用 | 请求内去重 | 同一 `(name, canonical_json(args))` 只执行一次；重复时返回缓存结果并标注 |

异常退出优先级：

1. **Provider 认证/配置错误**：记录 ERROR（不含密钥），立即走规则回退；不回显上游错误。
2. **Provider 限流 429**：按 `Retry-After`（上限 2s）有限重试；仍失败则回退；不产生重试风暴。
3. **超时/5xx/响应格式错误**：最多 `AI_LLM_MAX_RETRIES` 次指数退避；仍失败则回退。
4. **预算耗尽**：若已有成功 Tool 结果，返回“已查询到：<最后一条安全结果> + 请稍后重试”；否则返回统一超时文案。
5. **达到最大轮次**：同上，不继续调用模型。
6. **工具系统错误**：只读工具可重试 1 次；仍失败则把安全错误文本交给模型，由模型决定是否结束；写工具（未来）绝不重试。

---

## 5. 文件修改清单（本轮不实施）

### 5.1 新增文件

| # | 路径 | 内容 |
|---|---|---|
| 1 | `apps/api/src/app/ai/llm/__init__.py` | 导出 `LLMProvider`、`get_llm_provider` |
| 2 | `apps/api/src/app/ai/llm/base.py` | 协议、DTO、异常族、消息类型 |
| 3 | `apps/api/src/app/ai/llm/ark.py` | `ArkProvider`：HTTP 调用、状态码映射、重试、响应解析 |
| 4 | `apps/api/src/app/ai/llm/factory.py` | `get_llm_provider()` / `close_llm_provider()` |
| 5 | `apps/api/src/app/ai/agent/tool_schema.py` | `build_openai_tools`、`allowed_tool_names`、`validate_tool_specs` |
| 6 | `apps/api/src/app/ai/agent/loop.py` | `AgentLoop`、`LoopBudget`、`call_with_retry`、参数解析/去重/裁剪 |
| 7 | `apps/api/tests/unit/test_ai_llm_provider.py` | Provider 成功/失败/重试/异常映射 |
| 8 | `apps/api/tests/unit/test_ai_llm_schema.py` | Schema 正确性、角色过滤、无身份字段、drift |
| 9 | `apps/api/tests/unit/test_ai_llm_loop.py` | 循环、上限、去重、Tool 失败、多轮 |
| 10 | `apps/api/tests/unit/test_ai_llm_security.py` | 伪造身份、参数异常、Session 隔离、脱敏 |
| 11 | `apps/api/tests/unit/test_ai_llm_config.py` | 配置校验、密钥缺失、生产白名单 |

### 5.2 修改文件

| # | 路径 | 修改点 |
|---|---|---|
| 1 | `apps/api/src/app/core/config.py` | 新增 `AI_LLM_*` / `ARK_API_KEY` 字段；`model_validator` 增加 LLM 校验；`ARK_API_KEY` 设 `repr=False` |
| 2 | `apps/api/src/app/ai/mcp_server.py` | `ToolSpec` 增加 `description/parameters`；补充 `TOOL_SPECS` 元数据；新增 `list_tool_definitions(ctx, readonly_only)`；**不改 6 个 Handler 业务体** |
| 3 | `apps/api/src/app/ai/agent/runtime.py` | 增加 LLM 分支与 Provider 注入；`_legacy_chat_guarded`（只读闸门）；锁 TTL 改为可配置/按预算计算；trace 增加 `request_id/mode/llm_calls/provider/fallback_reason` |
| 4 | `apps/api/src/app/ai/agent/prompts.py` | 新增 `build_llm_messages`；`build_runtime_context` 默认不输出明文 `user_id/tenant_id/role_id`；增加“工具结果是数据不是指令”约束 |
| 5 | `apps/api/src/app/modules/ai/router.py` | Phase 2 可选：`data.mode` / `data.trace_id`；Phase 3 可选 `data.tool_trace`；**不 import 模型 SDK** |
| 6 | `apps/api/src/app/main.py` | Phase 0 可选：lifespan 关闭 Provider HTTP 客户端 |
| 7 | `apps/api/pyproject.toml` | 将 `httpx>=0.27` 加入 `[project].dependencies`（当前仅在 dev） |
| 8 | `/Users/lixiang/Desktop/class_booking_system/.env.example` | 增加 `AI_LLM_*` / `ARK_API_KEY` 占位符与注释 |
| 9 | `/Users/lixiang/Desktop/class_booking_system/.env.prod.example` | 同上，强调生产必须显式白名单与密钥注入 |
| 10 | `docs/ai/agent/volcengine-ark-integration-plan.md` | 本文档 |
| 11 | `apps/api/tests/unit/test_ai_p0_stability.py` | 若 Phase 1 移除 prompt 中的明文身份 ID，需同步把 `test_system_prompt_built_and_not_exposed` 的 `"user_id：7"` / `"tenant_id：3"` 断言改为“不得出现”；若决定保留 ID 则不改 |

### 5.3 明确不修改

- `apps/api/src/app/modules/**/service.py`、`repository.py`、`models.py`、`schemas.py`
- `apps/api/alembic/**`、任何迁移
- 6 个 Tool Handler 的业务实现（`query_courses`、`query_schedules_impl`、`get_my_bookings`、`get_my_balance`、`create_booking`、`cancel_booking`）
- `apps/api/src/app/middleware/rate_limiter.py`、租户中间件、`tenant_query.py`
- `apps/miniapp/**`（Phase 1 契约不变，无需前端改动）
- `apps/api/src/app/ai/tools/`（历史残留，不新增第三套实现）

---

## 6. 分阶段开发步骤

### Phase 0：配置与适配层（不改线上行为）

1. `core/config.py` 增加配置字段与 `model_validator`；`ARK_API_KEY` 仅环境变量；更新 `.env.example` / `.env.prod.example`。
2. `pyproject.toml` 增加直接依赖 `httpx>=0.27`，`uv lock` 同步。
3. 新增 `ai/llm/base.py`、`ark.py`、`factory.py`；实现 `/chat/completions` 请求、超时、重试、状态码映射、JSON 解析。
4. `mcp_server.py::ToolSpec` 增加 `description/parameters`；补齐 6 个 Tool 的 JSON Schema；新增 `list_tool_definitions`。
5. 新增 `agent/tool_schema.py`；增加 schema 自检（properties == input_fields、无身份字段）。
6. 全部能力默认关闭（`AI_LLM_ENABLED=false`）；新增单测使用 `httpx.MockTransport`，不联网、不连 DB。
7. 退出条件：现有 `tests/unit` 全部用例全绿（当前 9 个文件、131 个用例函数）；新增 Provider/Schema 测试通过；`ruff`、`mypy baseline` 通过；线上行为与当前完全一致。

### Phase 1：单轮 function calling（只读）

1. `prompts.py` 增加 `build_llm_messages`，默认不发送明文身份 ID；加入工具输出防注入约束。若移除 ID，需同步调整 `test_ai_p0_stability.py::test_system_prompt_built_and_not_exposed` 的断言（见 5.2 第 11 项）。
2. `runtime.py` 增加 `AI_LLM_ENABLED` 分支；调用 `AgentLoop`，`AI_LLM_MAX_TOOL_LOOPS=2`（一次工具往返）。
3. `AI_LLM_READONLY_ONLY=true`：
   - `list_tool_definitions` 只返回 `is_write=False` 的 Tool；
   - 规则回退中的 `create_booking` / `cancel_booking` 意图直接返回“请在小程序页面操作”，不执行 Tool。
4. Loop 内实现参数 JSON 解析、白名单、结构校验、Tool 结果裁剪、`role=tool` 消息。
5. Provider 异常统一走规则回退；`trace` 增加 `mode/request_id/llm_calls/fallback_reason`。
6. 退出条件：4 个只读 Tool 的端到端 mock 测试通过；教师/管理员看不到 `get_my_balance`；模型参数伪造身份不生效；只读闸门测试通过。

### Phase 2：多轮循环与超时预算

1. `AI_LLM_MAX_TOOL_LOOPS` 提升到 4；总预算 15s；每轮最多 2 个 tool call；总 tool 调用 ≤5。
2. 实现请求内去重（`(name, canonical_json(args))`）。
3. 实现模型调用重试：仅超时/5xx/429，指数退避 + 抖动，最多 `AI_LLM_MAX_RETRIES`；401/400 不重试。
4. 只读 Tool 瞬时 `system_error` 重试 1 次；写 Tool 永不重试。
5. 调整会话锁 TTL：`AI_LLM_TOTAL_BUDGET_MS + 5000ms`，避免 LLM 请求期间锁过期。
6. 历史裁剪：最近 `AI_LLM_HISTORY_MESSAGES=6` 条、单条 500 字符；不持久化 tool 消息；LLM 模式下清理遗留的 `selecting_schedule` / `confirming_cancel` 状态。
7. 退出条件：最大轮次、预算耗尽、重复调用、Tool 失败、多轮上下文测试全部通过；无死循环、无重复执行。

### Phase 3：测试、灰度与观测

1. 增加可选真实契约测试（不进入 CI 默认路径）：`ARK_CONTRACT_TEST=1` 时调用方舟 staging，验证 `tools` 支持、`tool_calls` 解析、`usage` 字段。
2. 灰度：`AI_LLM_ENABLED=true` + `AI_LLM_ENABLED_TENANTS` 指定 1 个内部租户 → 观察 24h → 扩到 10% 租户 → 全量。
3. 观测指标（基于结构化日志，不新增监控基础设施）：
   - `mode=llm` 占比、`llm_fallback` 占比；
   - Provider 错误率（401/429/5xx/timeout）；
   - 平均/ P95 延迟；
   - Tool 调用成功率、`business_error` 分布；
   - 每请求模型调用次数分布、token 用量。
4. 契约影响面：确认 4 端（admin/student/teacher/miniapp）仅 miniapp 消费 `/ai/chat`；Phase 2 新增可选字段不改变 `data.response`；若引入 `tool_trace`，同步更新 OpenAPI 文档说明并评估 `packages/api-types`。
5. 回滚：将 `AI_LLM_ENABLED=false`（或从白名单移除租户），无需回滚代码；规则链路保留完整能力。
6. 文档与规则更新（实施阶段执行）：在 `ai/ai-architecture.md` 增补 LLM 层边界；在 `docs/ai/agent/` 增补接入记录与灰度结论。

---

## 7. 测试策略（10 类）

所有新增测试必须满足：不依赖真实 DB / Redis / 网络；Provider 使用 `httpx.MockTransport` 或 fake provider；Tool 使用现有 monkeypatch 方式；`tests/unit/conftest.py` 已覆盖父级 DB/Redis fixture。

| # | 类别 | 测试要点 | 建议测试文件/用例 |
|---|---|---|---|
| 1 | 模型 API 成功 | 第一次返回 `tool_calls`，第二次返回最终文本；断言 `execute_tool` 被调用一次、最终 `data.response` 正确 | `test_ai_llm_loop.py::test_success_tool_then_answer` |
| 2 | 模型 API 失败 | 401/403/429/500/timeout/非法 JSON；断言不执行任何 Tool、走规则回退或统一错误文案、无上游原文/密钥/堆栈 | `test_ai_llm_provider.py`、`test_ai_llm_loop.py::test_provider_errors_fallback` |
| 3 | Schema 正确性 | 6 个 `ToolSpec.parameters.properties` == `input_fields`；枚举/范围/描述存在；无 `user_id/tenant_id`；`tools[]` 信封为 `type=function`；drift 测试对比 FastMCP 反射（若可用） | `test_ai_llm_schema.py::test_tool_schema_is_derived_from_tool_specs` |
| 4 | 角色过滤 | `student` → 4 个；`teacher/admin/super_admin` → 3 个且无 `get_my_balance`；无角色 → 0；角色查询异常 → 0（fail closed） | `test_ai_llm_schema.py::test_role_filtering_fail_closed` |
| 5 | 伪造身份 | 模型参数含 `user_id/tenant_id` 被 `_filter_arguments` 丢弃；`tools[]` 无身份字段；prompt 不含明文身份 ID；`execute_tool` 仍使用 `ToolContext` 的可信 ID | `test_ai_llm_security.py::test_llm_cannot_set_identity` |
| 6 | 参数异常 | 非 JSON 字符串、非 object、超长、未知键、错误类型、越界 `days`、非法日期、非法 status；断言不进入 Service，返回安全 tool 错误，无 traceback | `test_ai_llm_loop.py::test_invalid_arguments_not_executed` |
| 7 | Tool 失败 | `business_error` / `system_error` 的 tool message 格式；只读瞬时错误重试 1 次；写 Tool 永不重试；重复失败不无限循环 | `test_ai_llm_loop.py::test_tool_failure_handling` |
| 8 | 多轮 | 历史只取最近 6 条、单条 500 字符；tool 消息不入 Redis；第二轮能带上下文；LLM 模式不误用遗留 `selecting_schedule` 状态 | `test_ai_llm_loop.py::test_multi_turn_history_bounded` |
| 9 | 最大循环 | Provider 永远返回 `tool_calls`；断言模型调用次数 == `AI_LLM_MAX_TOOL_LOOPS`，Tool 调用 ≤5，最终返回兜底文本，无死循环 | `test_ai_llm_loop.py::test_max_loop_stops` |
| 10 | Session 隔离 / 超时限流 | 同一 `session_id` 不同 `user_id` 历史互不可见；两个用户 tools/结果不串；总预算耗尽；429 退避上限；中间件 20/60 限流不回归 | `test_ai_llm_security.py::test_session_isolation`、`test_ai_llm_loop.py::test_budget_exceeded`、`test_ai_agent_hardening.py`（复用） |

补充回归：

- 现有 `test_ai_agent_handler_contract.py`、`test_ai_agent_hardening.py`、`test_ai_p1_tool_platform.py` 必须全绿。
- 新增测试不得修改 `tests/integration` 既有用例；不得引入真实方舟 Key 到 CI。

---

## 8. 验收标准（可量化）

| # | 验收项 | 标准 |
|---|---|---|
| 1 | 架构边界 | 0 个 Service / Repository / Model / Migration 改动；Tool 仍只经 `execute_tool()` |
| 2 | 只读范围 | `AI_LLM_READONLY_ONLY=true` 时，`tools[]` 中写工具数量 = 0；规则回退也不执行写 Tool |
| 3 | 角色过滤 | `student` 可见 4 个只读 Tool；`teacher/admin/super_admin` 可见 3 个；无角色 0 个；角色查询异常 0 个 |
| 4 | Schema 一致性 | 6/6 `ToolSpec.parameters.properties` 与 `input_fields` 完全一致；身份字段出现次数 = 0 |
| 5 | 身份不可伪造 | 模型/前端传入 `user_id/tenant_id` 后，实际 Tool 使用的仍是 `ToolContext` 值；相关测试 100% 通过 |
| 6 | 循环上限 | 单请求模型调用 ≤ 4 次；Tool 调用 ≤ 5 次；无限 `tool_calls` 测试在 4 次内停止 |
| 7 | 超时预算 | 单请求 LLM 总耗时 ≤ 15s（硬上限）；超时后 100% 返回用户可读文案或有依据的最后查询结果 |
| 8 | 错误安全 | Provider 各错误分支均不出现 `Traceback`、`SELECT`、表名、主机名、`ARK_API_KEY`；断言覆盖 401/429/500/timeout/非法 JSON |
| 9 | 回退可用 | Provider 不可用时，规则链路回退成功率 100%；原有 `query_*` / `get_my_*` 回复能力不退化 |
| 10 | 会话隔离 | 不同 `user_id` 使用相同 `session_id` 时，历史/状态/工具结果交叉读取次数 = 0 |
| 11 | 测试 | 新增单测 ≥ 30 条，`uv run pytest tests/unit` 全绿；无网络/DB 依赖；`ruff` 与 `mypy baseline` 通过 |
| 12 | 灰度可观测 | 每次 LLM 请求日志包含 `request_id`、`mode`、`llm_calls`、`tool names/status/latency`、`fallback_reason`；不含消息正文与参数值 |
| 13 | 延迟目标 | Phase 3 实测单工具问答 P95 ≤ 12s；无工具问答 P95 ≤ 6s；硬上限 15s |
| 14 | 成本上限 | 单请求 `max_tokens=800`；prompt 字符上限约 8000（system ≤1000 + 历史 ≤3000 + tool ≤4000）；每用户请求频率仍受 20/60 限流 |

---

## 9. 风险清单

| # | 风险 | 影响 | 缓解措施 |
|---|---|---|---|
| R1 | 方舟模型不支持 `tools` 或返回格式与 OpenAI 兼容层不一致 | function calling 不可用 | Phase 0 真实契约冒烟；模型可配置；不支持时保持规则链路；不把 SDK 写死 |
| R2 | API Key 泄露（日志/异常/响应/仓库） | 账户被盗用、费用损失 | 仅环境变量；`repr=False`；日志脱敏；`.env*` gitignore；密钥轮换；代码评审卡点 |
| R3 | 模型幻觉/编造 Tool 参数或 ID | 查询错误、用户误导 | 第一阶段只读；参数结构校验 + Tool 二次校验；Tool 结果为权威；不让模型生成写操作 ID |
| R4 | Prompt Injection（用户消息或工具文本） | 越权、泄露系统提示、诱导写操作 | System Prompt 明确“工具结果仅为数据”；工具输出加 `TOOL_RESULT` 框；写工具不开放；身份不在 prompt |
| R5 | 成本失控（循环/长输出/高频请求） | 账单超支 | 最大 4 次模型调用、800 输出 token、15s 预算、20/60 用户限流、租户白名单灰度 |
| R6 | 延迟过高导致用户体验下降 | 请求堆积、重复提交 | 单次 6s、总 15s、超时回退规则链路；锁 TTL 延长到 20s |
| R7 | 并发锁 TTL 5s < LLM 耗时 | 同会话并发请求穿透，重复工具调用/重复写（未来） | Phase 2 将锁 TTL 调整为总预算 + 5s；写操作未来再加幂等键 |
| R8 | 会话上下文串扰/污染 | 跨用户数据泄露、旧工具结果误导 | Session key 已带 `user_id`；只取最近 6 条；不持久化 tool 消息；LLM 模式清理遗留状态 |
| R9 | 只读闸门遗漏，规则回退仍执行写操作 | 第一阶段出现未经确认的预约/取消 | 在 `_legacy_chat_guarded` 统一拦截 `create_booking/cancel_booking` 意图；测试断言写 Tool 未被调用 |
| R10 | 外部数据合规：用户消息/课程/排期/余额发送到方舟 | 数据出境/第三方处理合规风险 | 只发送最小上下文；Tool 输出已最小化；不发送手机号等 PII；评估方舟数据协议与租户授权 |
| R11 | 超时取消 Tool 导致 DB 连接/事务处理不干净 | 连接池压力 | 使用 `asyncio.wait_for` + Handler 内 `SessionLocal` 上下文退出；只读查询优先；监控连接池 |
| R12 | 响应契约新增字段导致前端假设变化 | 多端兼容问题 | Phase 1 不改契约；新增字段均为可选且默认关闭；同步评估 4 端；禁止流式字段 |
| R13 | 方舟 429/5xx 重试放大故障 | 雪崩、重复计费 | 仅幂等模型调用/只读 Tool 重试；指数退避 + 上限；401/400 不重试；熔断由总预算兜底 |
| R14 | 角色过滤与实际授权口径漂移 | 模型看到不该看的工具 | 过滤与执行共用 `get_user_role_codes` + `required_roles`；执行期 `_authorize` 二次校验；drift 测试 |

---

## 10. 暂不实施事项

1. **写操作**：`create_booking`、`cancel_booking` 不进入模型工具集；不实现 LLM 驱动的预约/取消。
2. **写操作确认机制**：未来需要的确认 token、dry-run、幂等键、单轮单写、确认时二次鉴权，本轮只设计不实现。
   - 建议方向：确认 token 存 `SessionManager` 状态（TTL 300s，绑定 `user_id/tenant_id/tool_name/args_hash`）；用户通过 UI 明确确认后才执行；确认时重新校验角色与租户；写 Tool 永不自动重试；Service 层行锁/状态重检继续作为最终防线。
3. **流式 SSE / WebSocket**：不引入；`/ai/chat` 保持一次性 JSON。
4. **真实 RAG / 向量库 / Embedding**：不接入；静态知识仍不伪装成检索结果。
5. **LangGraph / 多 Agent 编排框架**：不引入；使用最小 `AgentLoop`。
6. **MCP Client / 外部 MCP transport / stdio 独立进程**：不引入；继续进程内 `execute_tool`。
7. **新增业务 Tool**（会员卡列表、课程详情、排期详情、教师/教室等）：不在本阶段。
8. **多 Provider 路由 / 模型自动降级**：只实现 Ark 单 Provider；不实现跨厂商 fallback。
9. **Prompt 管理后台 / 可视化编排**：不实现；Prompt 仍在代码中版本化。
10. **成本看板 / 租户配额 / 计费系统**：不实现；只记录 token 与调用次数日志。
11. **前端 UI 改造**：Phase 1 契约不变，不改 `AiChatPanel`；未来若增加“工具执行状态/确认按钮”再单独评估。
12. **数据库结构变更**：不新增表/字段/迁移；会话与灰度均使用 Redis/环境变量。
13. **模型微调 / 评测集**：不实施；Phase 3 只做真实契约冒烟与灰度观测。

---

## 附录 A：不可违反的不变式（实施时逐条复核）

1. 身份链固定：`JWT → get_current_user → AgentRuntime → ToolContext → ContextVar → Service`；LLM 输出、用户消息、前端请求体都不得决定 `user_id/tenant_id`。
2. 所有 Tool 调用仍必须经过 `execute_tool(tool_name, arguments)`；禁止 Loop 直接调用 Handler、Repository、SQL 或 Redis。
3. `TOOL_SPECS` 是唯一 Tool 元数据源；`tools[]` 由它派生；Handler 业务实现不改。
4. 角色过滤复用 `get_user_role_codes` + `spec.required_roles`；不新建权限表、不依赖 `PERMISSION_CHECK_BYPASS`。
5. 第一阶段写工具不可见、不可执行；规则回退同样拦截写意图。
6. Router 不 import 模型 SDK；Provider 是唯一外部调用点；Runtime 只依赖协议。
7. 错误不回显内部细节；日志不记录消息正文、Tool 参数值、API Key。
8. 外部模型只接收最小必要上下文；Tool 结果文本必须裁剪并声明“仅为数据”。
9. 不引入 LangGraph、MCP Client、SSE、新迁移、新业务 Tool。
10. 任何契约新增字段必须可选、默认关闭、评估 4 端影响；删除/改语义属于破坏性变更，禁止在本阶段发生。

---

## 附录 B：方舟模型支持度与白名单确认（2026-11-09）

> 来源：火山方舟官方文档「模型列表」（更新于 2026-11-02）、「Function Calling」、「兼容 OpenAI SDK」、「Base URL 及鉴权」、「开通管理」。
> 本附录只做事实确认，不改变前文方案与不变式。

### B.1 接入形态确认

| 项目 | 结论 |
|---|---|
| 数据面 Base URL | `https://ark.cn-beijing.volces.com/api/v3`（Chat API：`POST /api/v3/chat/completions`） |
| 兼容性 | OpenAI 兼容（`openai>=1.0` SDK 或直接 HTTPS 均可） |
| `model` 取值 | 可直接用模型 ID（如 `doubao-seed-2-1-lite-260915`）；也兼容推理接入点 `ep-xxx` |
| Function Calling | Chat API `tools`（`type=function`）+ 响应 `choices[0].message.tool_calls`；支持单轮多个 `tool_calls` |
| `tool_choice` | `doubao-seed-1-6` 系列及之后支持 |
| `parallel_tool_calls` | 默认 `true`；设 `false` 时（`doubao-seed-1-6` 及之后）模型单轮最多返回 1 个工具调用 |
| 深度思考 | `doubao-seed-2-1` / `doubao-seed-2-0` / `doubao-seed-evolving` 带「深度思考」，默认开启；需在请求中传 `extra_body={"thinking":{"type":"disabled"}}` 关闭，否则延迟与 token 成本上升 |
| 流式 | 支持 `stream=true` 与 `delta.tool_calls`；本阶段不启用 |

### B.2 候选模型与默认限流（2026-11-02 模型列表）

| 模型 ID | 工具调用 | 结构化输出 | 上下文 | 最大 RPM | 最大 TPM | 建议 |
|---|---|---|---|---|---|---|
| `doubao-seed-2-1-lite-260915` | 支持 | 支持 | 1024k | 30000 | 5000000 | **Phase 1 默认**：高频 SaaS 场景、限流最宽 |
| `doubao-seed-2-1-pro-260915` | 支持 | 支持 | 1024k | 500 | 1000000 | 质量对照 / 复杂多轮评估 |
| `doubao-seed-evolving` | 支持 | 支持 | 1024k | 500 | 1000000 | Agent 能力迭代快，但版本周级变化，不作为默认 |
| `doubao-seed-2-0-lite-260428` | 支持 | 支持 | 256k | 30000 | 5000000 | **LTS 保守选择**（稳定性优先时） |
| `deepseek-v4-1-flash-261017` | 支持 | 支持 | 1024k | 3000 | 5000000 | 备选，不与豆包混用同一套 Prompt 时需重新评测 |

说明：

- 上表为账号级「模型级限流」默认值；同一主账号下同一基础模型的所有推理接入点共享该配额，超额需通过工单提额。
- 模型限流为「非刚性保障」，受平台负载影响；配置中的 20 次/分钟用户级限流仍需保留。
- Phase 1 建议 `AI_LLM_MODEL=doubao-seed-2-1-lite-260915`；若真实冒烟发现工具调用质量不足，再切换 `doubao-seed-2-1-pro-260915`（RPM 500，容量显著下降，需要灰度）。

### B.3 网络出网白名单（部署侧）

| 域名 | 端口 | 用途 | 是否本阶段必须 |
|---|---|---|---|
| `ark.cn-beijing.volces.com` | 443 | 数据面推理 API（唯一外部调用点） | **必须** |
| `ark.cn-beijing.volcengineapi.com` | 443 | 管控面 OpenAPI（开通模型、管理接入点、查配额） | 否（本阶段不调用） |

- 按**域名**放行，不按 IP：方舟数据面经 CDN 调度，IP 不稳定。
- 只需出站，不需要开放任何入站端口。
- 若部署环境强制代理，Provider 使用 `httpx` 并保持 `trust_env=True`，即可读取 `HTTPS_PROXY` / `NO_PROXY`。
- 不需要访问 `*.volcengine.com` 其他子域、对象存储或控制台页面。

### B.4 方舟侧「开通」与配额

1. 主账号需在方舟控制台「开通管理」开通目标模型；文本模型通常可直接开通，具体以控制台提示为准。
2. 模型级 `RPM/TPM` 不可手动调整，超出默认值需提交工单申请提额。
3. 推理接入点（Endpoint）限流可由用户自行配置，但本阶段直接使用模型 ID，不创建接入点。
4. 文本模型通常无额外申请门槛；官方文档中带余额/资源包条件的开通限制主要针对视频/图像类模型，本阶段不涉及。实际以控制台「开通管理」提示为准。

### B.5 应用侧白名单（建议新增配置）

| 配置项 | 作用 | 建议默认 |
|---|---|---|
| `ARK_API_KEY` | 方舟密钥，仅环境变量注入 | 必填，`repr=False` |
| `AI_LLM_BASE_URL` | 数据面地址 | `https://ark.cn-beijing.volces.com/api/v3` |
| `AI_LLM_MODEL` | 实际调用模型 | `doubao-seed-2-1-lite-260915` |
| `AI_LLM_ALLOWED_MODELS` | 模型白名单，防止误配视频/高价模型 | 上表 B.2 的 4 个文本模型 |
| `AI_LLM_ENABLED` | 总开关，关闭时完全走规则链路 | `false`（Phase 0/1 灰度前） |
| `AI_LLM_ENABLED_TENANTS` | 租户灰度白名单 | 空（空表示不启用） |

### B.6 仍需现场确认（无法从公开文档确认）

- ~~目标账号是否已开通 `doubao-seed-2-1-lite-260915`~~ → 已确认开通（见附录 C）。
- 账号实际 RPM/TPM 是否与模型列表默认值一致（合同/历史配额可能不同）。
- 生产环境出网策略是否已放行 `ark.cn-beijing.volces.com:443`（本机已验证通）。
- ~~关闭深度思考后的真实首 token 延迟~~ → 已实测（见附录 C）。

---

## 附录 C：接入冒烟与延迟实测（2026-11-14）

> 采集方式：`apps/api/scripts/verify_ark.sh`、`apps/api/scripts/bench_ark_ttft.py`。
> 环境：本机 macOS + 北京地域 `doubao-seed-2-1-lite-260915`，未经过生产网络。
> 本轮仅只读调用，未修改任何业务代码。

### C.1 三项冒烟结果

| # | 检查项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 网络连通性（`ark.cn-beijing.volces.com:443`） | PASS | 根路径返回 HTTP 401（未鉴权属正常） |
| 2 | 模型可用性 | PASS | 返回 `choices`，`total_tokens=65` |
| 3 | Function Calling | PASS | 返回 `tool_calls`，`function.name=query_schedules` |

### C.2 TTFT 实测（无 tools，每场景 20 次）

| 指标 | `thinking=disabled` | `thinking=enabled` | 倍数 |
|---|---|---|---|
| TTFT p50 | 0.62s | 13.28s | 21× |
| TTFT p95 | **1.29s** | **18.07s** | 14× |
| TTFT p99 | 1.41s | 20.97s | 15× |
| 端到端 p50 | 2.42s | 14.00s | 5.8× |
| 端到端 p95 | 3.42s | 19.02s | 5.6× |
| 端到端 p99 | 3.52s | 21.99s | 6.2× |
| 输出 token 均值 | 102 | 1049 | 10× |

### C.3 由实测数据确定的参数

| 参数 | 原方案值 | 实测结论 | 决定 |
|---|---|---|---|
| `AI_LLM_TIMEOUT_MS`（单次模型调用） | 6000 | 端到端 p99 = 3.52s，余量约 1.7 倍 | **保持 6000** |
| `AI_LLM_TOTAL_BUDGET_MS`（单请求总预算） | 15000 | 一次工具往返 ≈ 3.4 + 工具执行 + 3.4 ≈ 7–8s | **保持 15000** |
| `thinking` | 建议关闭 | 开启时 TTFT p95 18.07s > 15s 预算，且 token 翻 10 倍 | **请求体必须显式传 `{"thinking":{"type":"disabled"}}`，不依赖默认值** |

### C.4 实测暴露的两个必须落地项

**① 深度思考必须显式关闭**

`doubao-seed-2-1` 系列默认开启深度思考。开启状态下 TTFT p95 会直接超过总预算，等于 100% 超时；同时输出 token 从 102 涨到 1049，成本约 10 倍。Provider 必须固定写死关闭参数，不允许通过配置项放开。

**② LLM 产出的业务参数不可信**

冒烟中模型把「明天」解析成了 `{"date": "2025-05-22"}`（一个一年半前的日期），属于典型的参数幻觉。因此：

- System Prompt 必须注入服务端当前日期与时区（`Asia/Shanghai`），否则模型无法可靠换算相对时间。
- `query_schedules.date` 的 Tool 侧校验必须把「过去日期 / 超远未来日期」判为非法并返回友好提示，不能直接透传给 Service。
- 这条同时验证了方案 §3.5「LLM 参数不可信、只做结构校验、业务校验留在 Tool/Service」的必要性。

### C.5 尚未采集的数据

| 项 | 原因 | 什么时候补 |
|---|---|---|
| 带 `tools` 的 TTFT / 端到端 | 本轮未执行 `--with-tools` | 进入 Phase 1 前补测 |
| 真实 prompt（system + 历史）下的延迟 | 本轮为裸 prompt，输入仅 54 tokens | Phase 1 落地后用真实 Prompt 复测 |
| 生产网络（含出网策略/代理）延迟 | 本机环境无法代表生产 | Phase 3 灰度前在目标环境复测 |
| 账号实际 RPM/TPM | 需控制台「开通管理」核对 | Phase 0 编码前确认 |
