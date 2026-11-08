# 小程序 AI 助手 → Agent Runtime → MCP Server 的 Agent 化集成评估

> 目标链路：`Miniapp → FastAPI Agent API → Agent Runtime → 火山方舟/DeepSeek → MCP Client → MCP Server → Service`
> 当前状态：**无 LLM、无 MCP Client、无 RPC 协议**；仅“规则引擎 + 进程内 Tool 函数调用”
> 本文只做可行性评估与最小改造清单，**不重构代码、不安装依赖**
> 审计时间：2026-11-06
> **已按交叉验证修订（依据：`apps/api/src/app/ai/mcp_server.py:84-106,391-475,664-723,726-728`、`agent/runtime.py:700-755`，commit `08031c4`）**。修订明细见 `miniapp-mcp-validation-report.md` §1/§9。

---

## 1. 目标链路 vs 当前实现（逐段对照）

| 目标环节 | 当前实现 | 差距 | 状态 |
|---|---|---|---|
| Miniapp | `AiChatPanel` → `POST /api/v1/ai/chat`（JSON） | 无 | 已实现 |
| FastAPI Agent API | `modules/ai/router.py:59-81`，JWT + 租户头 | 无（可复用） | 已实现 |
| Agent Runtime | `runtime.py:86-181` 规则引擎、状态机、Redis | 缺规划/生成/工具选择能力 | 部分实现 |
| 火山方舟/DeepSeek | **不存在** | 需新增 LLM 适配器（全仓无 LLM SDK/HTTP 调用） | 未实现 |
| MCP Client | **不存在** | 需新增 Client + 身份绑定层 | 未实现 |
| MCP Server | `FastMCP("dance-saas-agent")` 已注册 6 个 Tool（`mcp_server.py:64,348-643`） | 仅注册，无 transport 在跑；`__main__` 的 stdio 无人调用（`726-728`） | 部分实现 |
| Service | Tool → Service → Repository → DB | 分层已正确，无需解耦 | 已实现 |

关键事实（本次实测）：
- `fastmcp 3.4.7` / `mcp 1.29.0`；
- `Client(mcp)` **in-memory transport 可用**：`await c.list_tools()` 返回 6 个工具名；
- 在同进程内，**ContextVar 能穿透 in-memory Client 调用**（用临时 FastMCP + `ContextVar` 实验验证 `ctx=trusted-user-1` 可被工具读到）；
- Tool schema 不含 `user_id/tenant_id`（`exclude_args` 已生效，但该参数在 3.4.7 已弃用）。

> 结论先行：**当前 Tool 资产可直接复用**；缺的是“LLM + 规划循环 + 受控 MCP Client”，而不是重写工具。

---

## 2. 十项可行性逐条回答

### 2.1 当前 Tool 能否直接供 Agent 使用？
**部分可行**。
- 工具已具备：名称/描述/参数 schema（FastMCP 注册）、四关校验、Service 复用、错误封套。
- 不可直接用的部分：
  1. 返回以**自然语言纯文本**为主，不便于 LLM 稳定解析（`mcp_server.py:381-388,432-448,509-523`）；仅 `query_schedules` 已返回结构化 `data`（`449-460`）；`ToolOutcome` 定义在 `mcp_server.py:84-96`；
  2. 身份依赖进程内 `ToolContext` ContextVar，**任何跨进程/外部 MCP Client 调用都会 401**（`mcp_server.py:678-687`）；
  3. `create_booking`/`cancel_booking` 没有“预演/确认”两阶段返回，LLM 直接调用会绕过产品确认要求。

### 2.2 是否需新增 MCP Client / Server？
- **Server：不需要新增**。`mcp` 单例已注册全部工具；只需为“Agent 调用”提供一种受控 transport。
- **Client：需要新增（但不是必须用 RPC）**。两条路线：

| 路线 | 做法 | 优点 | 缺点 | 建议 |
|---|---|---|---|---|
| A. 保留直接函数调用 | LLM 输出 `tool_name + args` → `execute_tool()`（现状） | 零改动、身份链天然正确、进程内调用成本最低 | 无 `tools/list` 动态发现；工具与 Runtime 强耦合；不像“MCP” | **第一阶段推荐**（工具清单可由 `TOOL_SPECS` 提供） |
| B. 进程内 MCP Client | `with tool_context(ctx): async with Client(mcp): await call_tool(name, args)` | 真实 MCP 语义（discover/call）；已验证 ContextVar 穿透；无网络面 | 每次调用有 SDK 序列化开销；需处理超时/异常映射；与 A 相比多一层协议适配 | 可选（第一阶段不推荐，见 validation report §8/§11） |
| C. 独立进程 stdio | 子进程 + stdio | 隔离性好 | **无身份通道**：stdio 无法携带 per-request user/tenant，所有 Tool 401；需自造 IPC 身份协议 | 不建议 |
| D. Streamable HTTP + 网关认证 | 新进程 + 公网/内网端点 | 可复用于外部 Agent | 新增网络攻击面与运维成本；需票据/限流/审计 | P2 再评估 |

### 2.3 Tool 是否需要调整？
需要，但**只做输出与确认语义，不动业务逻辑**：
1. 增加结构化结果字段（如 `ToolOutcome.data: dict | None`），保留 `text` 供现有规则引擎；**已完成（08031c4，仅 `query_schedules`）**（`mcp_server.py:92,449-460`）；
2. `query_schedules` 不再仅靠 `|` 文本协议，提供 `data.schedules[]`（同时保留 text 兼容现状，避免破坏 Runtime 解析与测试）；**已实现**（`mcp_server.py:449-460`，Runtime 优先消费 `data`：`runtime.py:712-727`）；
3. 写操作 Tool 增加“dry-run/预演”返回（或不落库的校验入口），供 Agent 做确认；
4. 工具描述补充“何时用/何时不用/参数示例”，供 LLM 选择（当前 description 较简略，`mcp_server.py:348-357` 等）。

**不需要调整**：`_gate` 四关、`ToolSpec` 角色矩阵、Service 调用方式。

### 2.4 Tool 与 Service 是否该解耦？
**已经解耦，且方向正确**：Tool 只调用 Service（`mcp_server.py:371-380,417-425,498-507,537-545,579-605,637-642`），无 Repository/裸 SQL/Redis 业务写入，符合 `layering.md`。
结论：**不要为了 Agent 化把业务规则下沉到 Tool 或 Runtime**；Agent 层只负责“选择工具、组织语言、确认策略”。

### 2.5 如何发现与调用工具？
推荐：
1. 第一阶段直接用 Server 端 `mcp.list_tools()`（实测可返回 6 个工具 schema）或 `TOOL_SPECS` 获取工具清单；无需 `Client(mcp)`；
2. 用现有 `TOOL_SPECS`（`mcp_server.py:161-180`）按 `ctx.role_id` 过滤，得到“本角色可见工具集”；
3. 把工具定义转成 LLM function-calling 格式（OpenAI/方舟兼容）；
4. LLM 返回 tool_calls → Runtime 校验白名单 → `await execute_tool(name, args, context=ctx)`（路线 A；若采用路线 B 则 `client.call_tool`）；
5. 只允许**白名单 + 角色过滤**后的工具，禁止模型自由构造工具名。
> 已验证 `Client(mcp)` in-memory 可用（本次实测列出 6 个工具）。调用时的身份 ContextVar 穿透也已用最小实验验证；仍需在真实 Runtime 中做集成测试确认（见 §5 未经验证）。**交叉验证复核：`mcp.list_tools()` 可在 Server 进程内直接获得同一份 schema，第一阶段不必引入 Client。**

### 2.6 结果如何返回给 LLM / 前端？
- Tool → Runtime：`ToolOutcome` 转成 `{ok, code, data, text}` 的 tool message，而不是只塞一段中文；
- LLM 生成最终自然语言 → `ChatResponse.response`；
- 建议新增 `tool_trace`（工具名/耗时/成功与否，不返回 SQL/堆栈），供前端展示“已为你查询…”，同时满足审计；
- 错误：Tool 已做业务/内部异常分离（`mcp_server.py:698-723`），Runtime 再做关键词映射（`runtime.py:579-612`）——接入 LLM 后应改为**结构化 error code 驱动文案**，避免模型编造。

### 2.7 Redis 职责（保留 + 扩展）
保留三件套（`session.py:39-57`）：
- 历史 `ai:session:*` TTL 3600；
- 中间态 `ai:state:*` TTL 600；
- 并发锁 `ai:lock:*` TTL 5s。

Agent 化后建议扩展：
| 用途 | Key | TTL | 说明 |
|---|---|---|---|
| LLM 工具调用幂等 | `ai:tool:idem:{user}:{tool}:{hash(args)}` | 60s | 防止模型重试导致重复写（尤其 create/cancel） |
| 限流计数 | `ratelimit:ai:{user}` | 60s | 配合 `RateLimiterMiddleware`（当前未注册） |
| 待确认动作 | `ai:confirm:{user}:{session}` | 300s | 写操作二次确认 token（替代/补充现有 state） |
| 只读结果短缓存（可选） | `ai:cache:schedules:{tenant}:{date}` | 30s | 降低高并发重复查询；需接受短暂不一致 |

**不要**把身份或权限缓存在 AI key 中；身份每次请求都从 JWT 重新取。

### 2.8 多租户与权限如何保留？
必须坚持三条：
1. 身份只来自 `get_current_user`（`deps/auth.py:62-64`）→ Runtime → `ToolContext`；**LLM 输入、tool_calls 参数、前端 body 一律不作为身份来源**；
2. 每次 Tool 调用前 `with tool_context(ctx)`，保证 `tenant_id` ContextVar 在调用栈内（`mcp_server.py:126-141`）；ORM 自动过滤依赖它（`tenant_query.py:40-80`）；
3. `_gate` 四关不变，`_filter_arguments` 继续丢弃身份字段（`mcp_server.py:659-661`）；工具发现要叠加角色过滤，避免把 `create_booking` 暴露给教师端模型。

额外建议：**System Prompt 中不要放真实 `user_id/tenant_id` 数字**（当前 `prompts.py:48-49` 有），改为“已认证学员（工号内部可见）”；数字身份只用于日志/审计。

### 2.9 Agent 层与 MCP 层职责边界

| 职责 | Agent 层（Runtime/LLM） | MCP 层（Server/Tool） |
|---|---|---|
| 意图理解、多轮对话、工具选择 | ✅ | ❌ |
| Prompt / 注入防护 / 输出语言组织 | ✅ | ❌（只做输出兜底） |
| 身份注入（从 JWT 到 ToolContext） | ✅（唯一入口） | ❌（不得接受外部身份） |
| 认证/授权/租户/入参四关 | ❌ | ✅ |
| 业务规则（名额、扣次、状态机） | ❌ | ❌（只在 Service） |
| 结果结构化与错误码 | 协作（消费） | ✅（产出） |
| 写操作确认策略 | ✅（决定是否执行） | ✅（提供预演/幂等） |
| 限流/审计 | ✅（入口） | ✅（逐工具） |

一句话：**Agent 决定“做什么”，MCP 决定“能不能做、对谁做”，Service 决定“业务上是否成立”。**

### 2.10 目标架构整体可行性
**可行，且改动可控**。最大风险不在技术栈，而在三处“契约”：
1. 工具返回值从“文本”升级为“结构化（含文本兼容）”；
2. 身份通道必须保持在进程内（不要让 LLM 或外部客户端持有身份）；
3. 写操作必须保留用户确认（`.trae/rules/ai/mcp.md` 明确要求）。

---

## 3. 推荐架构（目标态）

```mermaid
flowchart TD
    subgraph MP["小程序"]
        UI["AiChatPanel<br/>消息 / 确认按钮（新增）"]
    end

    subgraph API["FastAPI 进程"]
        R["POST /api/v1/ai/chat<br/>JWT + Tenant 中间件"]
        RT["AgentRuntime<br/>会话/锁/确认策略<br/>最多 3 轮工具循环"]
        LLM["LLM Adapter（新增）<br/>火山方舟 Ark / DeepSeek<br/>OpenAI 兼容 / aiohttp"]
        MC["MCP Client Adapter（新增）<br/>fastmcp.Client(mcp)<br/>list_tools / call_tool"]
        SP["System Prompt Builder<br/>（工具 schema + 安全指令）"]
        SM["SessionManager<br/>history / state / lock / confirm"]
        SRV["FastMCP Server（已有）<br/>6 Tools + _gate 四关"]
        SVC["Service → Repository → DB（已有）"]
        RD[(Redis)]
    end

    ARK["火山方舟 / DeepSeek API"]
    DB[(PostgreSQL)]

    UI -->|JSON| R --> RT
    RT --> SM --> RD
    RT --> SP
    RT -->|messages + tools| LLM --> ARK
    LLM -->|tool_calls| RT
    RT -->|角色过滤后的工具| MC
    MC -->|initialize / tools/list / tools/call| SRV
    RT -->|with tool_context(ctx)<br/>身份仅进程内| MC
    SRV --> SVC --> DB
    SRV -->|ToolOutcome{ok,code,data,text}| MC --> RT
    RT -->|最终回复 + tool_trace| R --> UI
```

> 注：图中 `MCP Client Adapter` 为**可选层**；第一阶段按 validation report §8/§11 使用路线 A（`execute_tool` 直调），MCP Client 仅在需要协议互操作/外部 Host 时启用。

关键设计点：
1. **身份不进 LLM**：Tool 调用包在 `with tool_context(ctx)` 内 / 或 `execute_tool(..., context=ctx)`；ContextVar 穿透已验证（§1）；
2. **不回退到外部 stdio**：stdio 子进程拿不到 per-request 身份，全部 Tool 会 401（`mcp_server.py:678-687`）；
3. **规则引擎保留**：LLM 超时/失败/未配置时回落到现有 `IntentRecognizer`；
4. **写操作两阶段**：LLM 只能“提议”，Runtime 生成 confirm token，用户在小程序点确认后才真正 `call_tool`；
5. **工具发现按角色**：`TOOL_SPECS` 与 DB 角色求交后才交给模型，避免“看见但不能用”的误导。

---

## 4. 最小改造清单（按优先级，不实施）

> 工作量级别：S ≈ 0.5 人日以内；M ≈ 0.5–2 人日；L ≈ 2–5 人日。全部为评估结论，非本次执行。

### P0（不完成则 Agent 链路跑不通）

| # | 改造 | 改动文件 | 工作量 | 说明 |
|---|---|---|---|---|
| P0-1 | `ToolOutcome` 增加结构化 `data`，保留 `text` | `apps/api/src/app/ai/mcp_server.py` | S | **已部分完成（08031c4）**：`query_schedules` 已填 `data`（`mcp_server.py:449-460`）；其余 5 个 Tool 仍为文本 |
| P0-2 | ~~新增“进程内 MCP Client + 身份绑定”适配器~~ | 新文件 `apps/api/src/app/ai/agent/mcp_client.py` | M（optional） | **交叉验证后下调优先级**：第一阶段直接用 `execute_tool()`（路线 A），MCP Client 仅在需要协议互操作/外部 Host 时再引入 |
| P0-3 | 新增 LLM 适配器（OpenAI 兼容） | 新文件 `apps/api/src/app/ai/agent/llm.py`；`core/config.py` 增加 `LLM_API_BASE/LLM_API_KEY/LLM_MODEL/LLM_TIMEOUT` | M | 用现有 `aiohttp`（`pyproject.toml:23`），不新增依赖；密钥只从环境变量读（`authentication.md` 要求） |
| P0-4 | Runtime 接入 LLM + 工具循环 + 规则回退 | `apps/api/src/app/ai/agent/runtime.py` | L | 最多 3 轮 tool loop；单次请求**最多一个写操作**；超时/异常回落 `IntentRecognizer`；保留现有锁与状态机 |
| P0-5 | 工具 schema 注入 System Prompt（动态） | `runtime.py`、`prompts.py` | S | 由 `list_tools` + `TOOL_SPECS` 角色过滤生成；保留现有安全指令（`prompts.py:20-27`） |
| P0-6 | 历史转为 LLM messages | `runtime.py`；复用 `session.get_context`（`session.py:108-117`） | S | 当前 `get_context` 已存在但无人调用；限制条数与长度，避免上下文膨胀 |

### P1（安全与体验必需，可与 P0 同批）

| # | 改造 | 改动文件 | 工作量 | 说明 |
|---|---|---|---|---|
| P1-1 | 消除文本协议注入面 | `mcp_server.py:432-460,651-656`；`runtime.py:700-755` | S | **已部分完成（08031c4）**：`_safe_cell` 转义 + Runtime 优先 `data`；文本回退路径仍在（安全审计 §6.2，风险中低） |
| P1-2 | 写操作二次确认 | `runtime.py`（confirm token）；`apps/miniapp/src/components/AiChatPanel.vue`（确认 UI） | M | 服务端生成 `pending_action`，前端确认后再发“确认”请求；Tool 侧提供幂等键（`ai:tool:idem`） |
| P1-3 | 注册限流中间件 | `apps/api/src/app/main.py:205-213` | S | `RateLimiterMiddleware` 已存在（`middleware/rate_limiter.py:235`）但从未注册；AI 路由按 user 限流 |
| P1-4 | `session_id` 入参校验 | `apps/api/src/app/modules/ai/router.py:30-32` | S | 长度 ≤64、字符集 `[A-Za-z0-9_-]`；避免超长 Redis key |
| P1-5 | 工具 trace / 审计 | `modules/ai/router.py:59-81`；`runtime.py:196-210` | S | 复用现有 trace 日志，增加 `tool_calls[]`（名称、耗时、ok）；不返回 SQL/堆栈 |
| P1-6 | `execute_tool(context=...)` 收敛为内部 API | `mcp_server.py:664-723` | S | 改为私有（如 `_execute_tool`）或加断言“仅允许 Runtime 调用”，为未来外部化立边界 |

### P2（外部 Agent / 规模化）

| # | 改造 | 改动文件 | 工作量 | 说明 |
|---|---|---|---|---|
| P2-1 | 外部 Agent 的 MCP HTTP transport + 认证票据 | 新模块 + `infra/docker` | L | OAuth2/mTLS + 每请求票据换 `ToolContext`；不暴露公网；见安全审计 §11 |
| P2-2 | 角色感知的工具发现 | `mcp_client.py`、`mcp_server.py` 元数据 | M | 按角色返回可用工具子集；避免模型被告知不可用工具 |
| P2-3 | SSE 流式回复 | `modules/ai/router.py`；`AiChatPanel.vue` | L | 当前契约为一次性 JSON，改动需同步前端与契约文档 |
| P2-4 | Tool 输出完整 JSON Schema | `mcp_server.py` | M | 与 P0-1 衔接；为外部 Agent 提供稳定契约 |
| P2-5 | Redis 限流/幂等/短缓存 | `session.py` 或新 `ai/agent/cache.py` | M | 见 §2.7；注意 TTL 与租户隔离 |

---

## 5. 未经验证 / 需要在实施前确认

1. **未经验证**：`with tool_context(ctx)` 包裹 `Client.call_tool` 在真实并发/多 worker 下 ContextVar 是否始终穿透（本次仅在单进程、单事件循环、简单工具上验证成功）。
2. **未经验证**：火山方舟 / DeepSeek 具体模型是否支持当前所需的 function-calling 协议与并发配额（未做联网验证，仓库内无相关配置）。
3. **未经验证**：生产环境是否已有外部 Agent 或第三方 MCP 客户端接入（仓库内无证据，见调用链文档 §8）。
4. **未经验证**：`aiohttp` 在生产 API 进程中的连接池/超时参数是否满足 LLM 长耗时调用（需压测）。
5. **未经验证**：`exclude_args` 弃用后，FastMCP 升级到新版本是否仍保证身份参数不进入 schema（当前版本实测可用，但已告警）。
6. **未经验证**：小程序端是否有能力承载“确认按钮 + 工具执行中”的交互状态（现有 `AiChatPanel` 只有 sending/loading，`AiChatPanel.vue:235-279`）。

---

## 6. 明确不做什么（防止过度改造）

- 不把业务规则（名额、扣次、状态机）搬进 Runtime 或 LLM Prompt；
- 不把 `FastMCP` 改为独立公网服务（当前无此需求，且会扩大攻击面）；
- 不删除规则引擎（它是 LLM 故障时的确定性回退）；
- 不修改 Service/Repository 的既有事务与租户逻辑；
- 不在本次审计中安装任何依赖、修改任何业务代码或迁移。
