# Miniapp MCP 审计交叉验证报告（第二轮）

> 验证对象：`docs/ai/mcp-audit/` 下 6 份审计文档
> 验证基准：当前工作区真实代码（含提交 `08031c4` 之后的变更）
> 验证方式：只读代码 + 反射 FastMCP 工具 Schema + 运行 `tests/unit/test_ai_p1_tool_platform.py`（23 passed）
> 验证时间：2026-11-06
> 约束：本报告不修改任何业务代码、配置、迁移、测试、依赖；只修订 Markdown 审计文档

---

## 0. 结论摘要

- 6 份文档的**主线结论正确**：`/ai/chat` 不经过 MCP 协议、无 MCP Client、无 LLM、身份来自 JWT、Tool 只调 Service。
- 但 6 份文档均存在**行号整体漂移**（生成于 `08031c4` 之前）；另有 4 类**结论过期**：
  1. `create_booking` 业务失败已改为 `ToolBusinessError` → `business_error`，“假成功”问题已修复；
  2. `query_schedules` 已有结构化 `ToolOutcome.data`，Runtime 优先消费 `data`，不再只依赖文本协议；
  3. `_safe_cell` 已对排期/预约文本做分隔符与换行转义，文本注入风险由“中”降为“中低”；
  4. `_require_student_role` 并非“全仓无调用”，测试文件仍引用它。
- 另外发现一处**代码/测试漂移**：`TOOL_SPECS["query_schedules"].handler_name` 已改为 `query_schedules_impl`，但 `tests/test_agent_runtime.py:201,234` 仍 monkeypatch `query_schedules`；该测试不在 CI 路径内（CI 只跑 `tests/unit` 与 `tests/integration`），因此未被暴露（详见 §6.2）。

---

## 1. 六份文档准确度评价

状态口径：**正确 / 部分正确 / 错误 / 无法验证**。行号类问题统一记为“部分正确（行号过期）”。

### 1.1 `miniapp-mcp-overview.md`

| # | 条目 | 状态 | 文档原文 → 真实代码 → 修正说明 |
|---|---|---|---|
| 1 | `/ai/chat` 不走 MCP 协议 | 正确 | 无 Client / 无握手；`runtime.py:19` 直接 import `execute_tool` |
| 2 | `mcp.run(transport="stdio")` 仅在 `__main__` | 正确 | 真实位置 `mcp_server.py:726-728`（原文 `666-668`，已修订） |
| 3 | `execute_tool` 进程内直调 | 正确 | 真实范围 `mcp_server.py:664-723`（原文 `614-644`，已修订） |
| 4 | 6 个 Tool、无 Resource/Prompt | 正确 | 6 个 `@mcp.tool`：`348,463,478,526,553,615`（原文行号已修订） |
| 5 | 文件行数 `mcp_server.py=668`、`runtime.py=793` | 部分正确（过期） | 真实 `728`、`810`，已修订 |
| 6 | ToolOutcome 字段只有 `kind/text/code/ok` | 部分正确（过期） | 真实已有 `error_type/data`（`mcp_server.py:84-96`），已修订类图 |
| 7 | “写操作 Tool 假成功”（§8-2） | **错误（已修复）** | 原文“`return` 文本 `543,550` 被包成 success” → 真实 `raise ToolBusinessError`（`581,588-592`）+ `execute_tool` 映射 `business_error`（`698-705`）；已改写为已修复 |
| 8 | 预约结果 `course_name=None` | 正确 | `booking/service.py:252,368,1513-1515`；Tool 输出 `mcp_server.py:606-612,643` |
| 9 | `upcoming` 参数死代码 | 正确 | `intent.py:143-146` 写入、`runtime.py:309-315` 不传、`mcp_server.py:478-523` 不接收 |
| 10 | 无速率限制 | 正确 | `main.py` 仅定义 `RATE_LIMIT_CONFIG`（209-213），全仓无 `add_middleware(RateLimiterMiddleware)` |
| 11 | 四关顺序与实现 | 正确 | `_gate` `212-250`（原文 `201-239`，已修订） |
| 12 | `exclude_args` 已弃用 | 正确 | 实测导入产生 `FastMCPDeprecationWarning`；6 处使用已更新行号 |

### 1.2 `miniapp-mcp-code-analysis.md`

| # | 条目 | 状态 | 文档原文 → 真实代码 → 修正说明 |
|---|---|---|---|
| 1 | 文件长度 668 / 793 | 部分正确（过期） | 728 / 810，已修订 |
| 2 | `ToolOutcome 84-95`、`ToolContext 98-104`、`_gate 201-239` 等符号表 | 部分正确（行号过期） | 已按真实行号整体更新；补充 `ToolBusinessError 99-106`、`_safe_cell 651-656`、`_filter_arguments 659-661` |
| 3 | `_require_student_role` 为死代码 | **错误** | 原文“全仓无调用（仅定义处命中）” → 真实被 `tests/test_mcp_tool_authorization.py:20,165,225` 引用；已改为“业务代码无调用、仅测试引用” |
| 4 | 业务失败字符串被包成 success | **错误（已修复）** | `mcp_server.py:581,588-592,698-705`；已改为“已修复（08031c4）” |
| 5 | 身份注入与四关顺序 | 正确 | `execute_tool` 678-687/692/694；`_gate` 213-248 |
| 6 | 每个 Tool 自建 SessionLocal | 正确 | `364,406,490,532,567,629` |
| 7 | Runtime 无 LLM、规则意图、Redis 状态机 | 正确 | `runtime.py:57,100` 注释明确“当前无真实 LLM 调用点” |
| 8 | `_parse_schedules` 纯文本解析 | 部分正确（过期） | 真实签名 `_parse_schedules(raw, data=None)`，优先 `data`（`700-755`） |
| 9 | 会话 key / TTL | 正确 | `session.py:39-57,92-96`；history TTL 3600、max 10 轮 |
| 10 | 开放问题（无 trace_id、exclude_args 弃用等） | 正确 | 仍成立 |

### 1.3 `miniapp-mcp-tools-inventory.md`

| # | 条目 | 状态 | 文档原文 → 真实代码 → 修正说明 |
|---|---|---|---|
| 1 | 6 个 Tool 名称 / 角色 / 是否写 / 入参 | 正确 | 反射 `mcp.list_tools()` 与 `TOOL_SPECS` 一致 |
| 2 | 注册行号与函数体行号 | 部分正确（行号过期） | 已整体更新（如 `query_courses 348-388`、`create_booking 553-612`） |
| 3 | `query_schedules` 只有文本返回 | **错误（过期）** | 真实 `query_schedules_impl` 返回 `ToolOutcome(data={"schedules": [...]})`（`391-460`）；MCP 入口只返回 `text`（`463-475`）；已补充说明 |
| 4 | `create_booking` 无卡返回字符串 → 假成功 | **错误（已修复）** | 原文 `return recommend.message`（`549-550`）→ 真实 `raise ToolBusinessError`（`587-592`）；已改为已修复 |
| 5 | `create_booking` 租户分支返回字符串 | **错误（已修复）** | 真实 `raise ToolBusinessError("排期不存在",404)`（`580-581`） |
| 6 | `_filter_arguments` 清空外部参数 | 正确 | `659-661` |
| 7 | Service 调用链 | 正确 | `371-380,417-425,498-507,537-545,579-605,637-642` |
| 8 | 文本协议风险 | 部分正确（已缓解） | `_safe_cell 651-656` + Runtime 优先 `data 712-727`；风险由高降为中低 |
| 9 | 测试覆盖“无卡假成功无用例” | 部分正确（过期） | 已新增 `business_error` 用例（`tests/unit/test_ai_p1_tool_platform.py:356-371`） |
| 10 | 魔法值/枚举/角色两套等风险 | 正确 | 仍成立 |

### 1.4 `miniapp-mcp-call-flow.md`

| # | 条目 | 状态 | 文档原文 → 真实代码 → 修正说明 |
|---|---|---|---|
| 1 | 全链路不经过 MCP 握手 | 正确 | `runtime.py:19,256`；`mcp_server.py:690-694,726-728` |
| 2 | 小程序 → FastAPI → Runtime → execute_tool | 正确 | 无 MCP Client |
| 3 | 四关与参数过滤 | 正确 | `_gate 212-250`、`_filter_arguments 659-661` |
| 4 | Tool 返回“自然语言纯文本（不是结构化 DTO）” | **部分错误（过期）** | `query_schedules` 已返回结构化 `data`（`449-460`）；只 MCP 入口为文本；已修订 |
| 5 | 异常封套只区分 DanceSaasException / 其他 | 部分正确（过期） | 新增 `ToolBusinessError` 分支（`698-705`）；已修订 |
| 6 | stdio 入口无人调用、无身份 → 401 | 正确 | 真实 `726-728`、`678-687` |
| 7 | 每个 Tool 自建 SessionLocal | 正确 | `364,406,490,532,567,629` |
| 8 | 无 MCP Server 独立进程/端口 | 正确 | Dockerfile / compose / CI 均无 MCP 启动项 |
| 9 | 限流未注册 | 正确 | `main.py:209-213`、`middleware/rate_limiter.py:235` |
| 10 | 行号整体漂移 | 部分正确（过期） | 已修订关键行号 |

### 1.5 `miniapp-mcp-security-audit.md`

| # | 条目 | 状态 | 文档原文 → 真实代码 → 修正说明 |
|---|---|---|---|
| 1 | JWT → ContextVar → ToolContext 链路 | 正确 | `deps/auth.py:40-66`；`router.py:47-56`；`runtime.py:232-244` |
| 2 | Tool 授权不使用 `PERMISSION_CHECK_BYPASS` | 正确 | `_authorize` 直接 `get_user_role_codes`（`196-209`）；checker 的 bypass 只在 `check_*` 中 |
| 3 | 四关顺序与 fail-closed | 正确 | `212-250`、`checker.py:455-457` |
| 4 | 跨租户多层拦截 | 正确 | `236-248`、`user/service.py:519-531`、`tenant_query` |
| 5 | `create_booking` 租户不符“返回排期不存在” | **错误（已修复）** | 已改为抛 `ToolBusinessError`（`580-581`），分类 business_error |
| 6 | 排期文本协议未转义、可注入伪造选项 | **错误（已缓解）** | `_safe_cell`（`651-656`）替换 `\|`/换行；Runtime 优先 `data`；已改为“已缓解，中低” |
| 7 | `/ai/chat` 无限流 | 正确 | `main.py:209-213` 只有配置，无注册 |
| 8 | `x-tenant-id` 不校验状态、租户不一致静默覆盖 | 正确 | `tenant_middleware.py:120-127` vs `130-145`；`auth.py:62` |
| 9 | 无 SQL/堆栈泄露；Redis 明文历史 1h | 正确 | `mcp_server.py:76-81,183-188,698-723`；`session.py:72-98` |
| 10 | 无高危急；`execute_tool(context)` 为信任边界 | 正确 | `execute_tool` 仅被 Runtime 与测试调用 |
| 11 | 行号整体漂移 | 部分正确（过期） | 已修订关键行号 |

### 1.6 `miniapp-mcp-agent-integration.md`

| # | 条目 | 状态 | 文档原文 → 真实代码 → 修正说明 |
|---|---|---|---|
| 1 | 无 LLM、无 MCP Client、无 RPC | 正确 | 全仓无 LLM SDK/HTTP 调用（`runtime.py:57,100` 注释确认） |
| 2 | Tool 资产可复用、只调 Service | 正确 | `mcp_server.py:371-380...637-642` |
| 3 | 结构化 `data` 尚未实现（P0-1） | **过期** | `query_schedules` 已实现（`449-460`）；其余 5 个仍为文本 |
| 4 | 文本注入面未消除（P1-1） | **过期（部分）** | `_safe_cell` + `data` 优先已落地；文本回退仍在 |
| 5 | 路线 B（进程内 MCP Client）作为 P0 推荐 | **结论调整** | 第一阶段改用路线 A（`execute_tool` 直调），B 降为可选；理由见 §8/§11 |
| 6 | `ToolOutcome` 只到 `text/code` | 部分正确（过期） | 真实含 `data/error_type`（`84-96`） |
| 7 | `fastmcp 3.4.7` / `mcp 1.29.0` | 正确 | 实测版本一致 |
| 8 | ContextVar 可穿透 in-memory Client | 无法验证 | 原文称“已用最小实验验证”，本轮未复现；仅能确认 FastMCP 3.4.7 支持 in-memory Client。标注“无法验证” |
| 9 | 火山方舟/DeepSeek function-calling 能力 | 无法验证 | 仓库无配置、未联网验证 |
| 10 | 行号漂移 | 部分正确（过期） | 已修订关键行号 |

---

## 2. MCP 实际实现情况（逐项）

| 维度 | 是否存在 | 证据（文件:行号 / 函数） | 说明 |
|---|---|---|---|
| **MCP Server（协议服务）** | 否（仅对象） | `apps/api/src/app/ai/mcp_server.py:64` `FastMCP("dance-saas-agent")` | 对象被 FastAPI 进程 import；未启动 transport |
| **MCP Client** | 否 | 全仓 grep 无 `fastmcp.Client` / `mcp.Client` / `stdio_client` | Runtime 直接 import `execute_tool`（`runtime.py:19`） |
| **MCP Host** | 否 | 无 Host 进程/配置；Dockerfile、compose、CI 均无 MCP 启动项 | FastAPI 只是宿主进程，不是 MCP Host |
| **协议握手 `initialize`** | 否 | 无 JSON-RPC 调用；`mcp.run` 仅 `__main__`（`mcp_server.py:726-728`） | 业务路径没有任何 initialize |
| **transport** | 代码存在、运行不存在 | `mcp.run(transport="stdio")`（`726-728`）；无 streamable-http / SSE | 部署与 CI 未启动该模块；即使启动也无身份上下文 → 全部 401（`678-687`） |
| **tools/list（协议）** | 否 | 无 `tools/list` JSON-RPC；HTTP `/api/v1/ai/intents` 是意图清单不是工具清单（`modules/ai/router.py:110-119`） | Server 内部 `mcp.list_tools()` 可列出 6 个工具（本轮实测）；`@mcp.tool` 已生成 Schema |
| **tools/call（协议）** | 否 | `execute_tool` 直调 `globals()[handler_name]`（`mcp_server.py:690-694`） | 无 JSON-RPC `tools/call` |
| **MCP session** | 否 | 无 MCP session 对象 | 业务会话是 Redis：`ai:session:*` / `ai:state:*` / `ai:lock:*`（`session.py:39-57`） |
| **Tool 注册** | 是 | 6 个 `@mcp.tool`：`348,463,478,526,553,615`；`TOOL_SPECS` `161-180` | Tool Schema 不含 `user_id/tenant_id`（`exclude_args` 生效，但已弃用告警） |
| **协议版本** | 无法验证 | 依赖 `fastmcp 3.4.7` / `mcp 1.29.0`（实测 `importlib.metadata`） | 未握手，无法确认协商后的 protocol version；代码与依赖 manifest 均未固定 |
| **Resources / Prompts** | 否 | 无 `@mcp.resource` / `@mcp.prompt` | 仅 tools |

补充实测：
- `mcp.list_tools()` 返回 6 个工具，参数 Schema 与 `TOOL_SPECS.input_fields` 一致，且均不含 `user_id/tenant_id`。
- `TOOL_SPECS["query_schedules"].handler_name == "query_schedules_impl"`（`166`）。
- `tests/unit/test_ai_p1_tool_platform.py` 运行结果：**23 passed**。

6 个 `@mcp.tool` 的注册名 / Schema / 源码位置（`exclude_args` 均为 `["user_id","tenant_id"]`）：

| Tool | 参数 Schema（实测） | 源码位置 | handler_name |
|---|---|---|---|
| `query_courses` | `keyword`, `category`, `level` | `348-388` | `query_courses` |
| `query_schedules` | `date`, `keyword`, `days` | MCP 入口 `463-475`；实现 `391-460` | `query_schedules_impl` |
| `get_my_bookings` | `status` | `478-523` | `get_my_bookings` |
| `get_my_balance` | 无 | `526-545` | `get_my_balance` |
| `create_booking` | `schedule_id`, `membership_card_id` | `553-612` | `create_booking` |
| `cancel_booking` | `booking_id`, `reason` | `615-643` | `cancel_booking` |

---

## 3. 已实现功能清单

1. **6 个 Tool 的 FastMCP 注册与 Schema**：`query_courses`、`query_schedules`、`get_my_bookings`、`get_my_balance`、`create_booking`、`cancel_booking`（`mcp_server.py:348-643`）。
2. **Tool 元数据单一源**：`ToolSpec(name/handler_name/required_roles/is_write/input_fields)` + `TOOL_SPECS`（`149-180`）。
3. **四关校验**：认证（ContextVar）→ 授权（DB 角色）→ 租户（ContextVar + 用户归属）→ 入参白名单（`196-310`）。
4. **统一错误封套**：`success / business_error / validation_error / system_error`；`ToolBusinessError` 与 `DanceSaasException` 均映射 business_error（`664-723`）。
5. **敏感信息兜底**：`_INTERNAL_PATTERN` + 200 字符上限（`76-81,183-188`）。
6. **六工具均复用 Service**，不直连 Repository / SQL / Redis 业务写入。
7. **排期结构化输出**：`ToolOutcome.data={"schedules":[...]}`（`449-460`），MCP 入口仍返回文本（`463-475`）。
8. **文本单元格转义**：`_safe_cell` 替换 `|`、折叠换行、剔除控制字符（`651-656`）。
9. **规则意图引擎**：关键词/正则识别 7 类意图（`intent.py`，217 行），不依赖 LLM。
10. **多轮状态机**：选排期 → 数字选择 → 预约；取消前确认（`runtime.py:415-573`）。
11. **Redis 会话三件套**：history（TTL 3600、max 10 轮）、state（TTL 600）、lock（TTL 5s），key 带 user 前缀（`session.py:39-57`）。
12. **trace 日志**：step_ms、intent、params、status、system_prompt 指纹（`runtime.py:99-170`）。
13. **小程序 AI 面板与 HTTP 封装**：`AiChatPanel.vue` → `aiChatApi`，纯 HTTP，无 MCP 依赖。
14. **stdio 入口代码**（未运行）：`mcp_server.py:726-728`。

---

## 4. 尚未实现功能清单

1. **MCP 协议栈**：无 Client、无 Host、无 `initialize`、无 `tools/list`、无 `tools/call`、无 MCP session。
2. **可运行 transport**：stdio 仅有 `__main__` 入口且无身份通道；无 HTTP/SSE transport；部署与 CI 未启动。
3. **LLM 调用**：无任何模型 SDK/HTTP 请求；`SYSTEM_PROMPT` 只组装、记录指纹，从未发送给模型（`runtime.py:57,100`）。
4. **其余 5 个 Tool 的结构化输出**：`get_my_bookings`、`get_my_balance`、`create_booking`、`cancel_booking`、`query_courses` 仍只返回文本。
5. **写操作的 dry-run / 服务端确认 token**：`create_booking` 在用户选号后直接落库；无预演与幂等键。
6. **限流**：`RateLimiterMiddleware` 类存在但未注册（`main.py:209-213`）。
7. **逐 Tool 审计 / 幂等**：无 tool 级 trace 结构、无 `ai:tool:idem:*`。
8. **流式回复**：`/ai/chat` 为一次性 JSON，无 SSE。
9. **`session_id` 校验**：仅 `str | None`，无长度/字符集约束（`router.py:30-32`）。
10. **外部 Agent 接入**：无票据、无 mTLS/OAuth2、无租户白名单。
11. **真实 RAG**：`ai/rag/retriever.py` 为硬编码 stub；`embedder.py` LLM 调用被注释。
12. **工具动态发现 / 角色过滤后的工具清单**：`TOOL_SPECS` 静态存在，但无对外 `list_tools_for_role` API。
13. **`upcoming` 参数链路**：意图写入但未传给 Tool。

---

## 5. 关键架构问题

1. **“MCP”名不副实**：只有 FastMCP 注册表 + 休眠 stdio，业务链路是普通函数调用；不能称为“已实现 MCP 服务”。
2. **双入口漂移，已出现实际后果**：
   - `TOOL_SPECS["query_schedules"].handler_name = "query_schedules_impl"`（`mcp_server.py:166`），MCP 注册的 `query_schedules` 只是文本包装（`463-475`）。
   - `tests/test_agent_runtime.py:201,234` 仍 monkeypatch `query_schedules`，但 `execute_tool` 调用的 `query_schedules_impl` 未被替换 → 该测试若真实运行会打到真实 DB；它位于 `tests/` 根目录，不在 CI 的 `tests/unit|integration` 路径（`.github/workflows/ci.yml:66,86`），因此长期未被发现。
3. **三处能力清单需同步修改**：新增 Tool 要同时改 `@mcp.tool` 函数、`TOOL_SPECS`、`INTENT_TOOL_MAP`（`runtime.py:23-30`）与 `intent.py` 关键词；缺少统一注册表派生机制。
4. **文本协议作为回退契约**：`_safe_cell` 与 `data` 已缓解，但 `_parse_schedules` 文本回退（`runtime.py:729-755`）仍与 Tool 输出格式耦合。
5. **错误语义三层翻译**：Tool（`ToolBusinessError/DanceSaasException`）→ `execute_tool` 封套 → Runtime 中文关键词映射（`579-612`）→ LLM 接入后再加一层；建议改由 error code 驱动文案。
6. **Prompt 已构建但无消费者**：`build_system_messages` 每请求执行，写入 trace 指纹，但无 LLM 调用；属于“为未来预留”的半成品。
7. **每个 Tool 自建 `SessionLocal`**：读操作可接受；Agent 多工具连续调用时，多次独立事务可能看到中间状态，需在 Agent 层避免跨调用依赖同一快照。
8. **写操作确认策略不完整**：取消有“是/确认”状态机；预约仅有“选择排期号”隐式确认，不符合 `ai/mcp.md` 的“写操作需用户确认”要求。
9. **同步入口无背压控制**：`/ai/chat` 无线程/请求级限流，长文本（500 字）会触发同步规则处理；接入 LLM 后成本与延迟风险放大。

---

## 6. 安全风险（高/中/低）

### 6.1 高风险

- **无**。当前无外部 MCP RPC 入口，未发现可直接跨租户/越权/命令执行的问题。

### 6.2 中风险

| 编号 | 风险 | 依据 | 说明 |
|---|---|---|---|
| M-1 | `execute_tool(context=...)` 是公共可传参入口，调用方可伪造 `ToolContext` | `mcp_server.py:664-723` | 当前仅 Runtime/测试调用；一旦被 HTTP 端点或外部 Agent 复用即绕过四关。建议私有化 + 断言 |
| M-2 | `/api/v1/ai/chat` 无限流 | `main.py:209-213`；`middleware/rate_limiter.py:235` | 任意登录用户可高频请求；接入 LLM 后直接放大成本 |
| M-3 | 写操作缺少服务端二次确认 | `runtime.py:453-470`；`mcp_server.py:601-605` | 用户选号即落库；无 dry-run / confirm token / 幂等键 |
| M-4 | `session_id` 未校验 | `modules/ai/router.py:30-32`；`session.py:39-57` | 可构造超长/特殊字符 Redis key；虽带 user 前缀无法跨用户，但可浪费内存 |
| M-5 | 文本回退解析仍存在 | `runtime.py:729-755` | `_safe_cell` 已转义当前字段；新增未转义字段仍可能伪造选项（中低） |

### 6.3 低风险

| 编号 | 风险 | 依据 | 说明 |
|---|---|---|---|
| L-1 | 中间件租户与 JWT 租户不一致时静默覆盖 | `tenant_middleware.py:95`；`auth.py:62` | 不造成越权，但审计日志难以发现探测 |
| L-2 | `x-tenant-id` 分支不校验租户存在/ACTIVE | `tenant_middleware.py:120-127` | AI 链路被 JWT 覆盖；结构风险 |
| L-3 | `tenant_query` 在 ContextVar 为空时跳过注入 | `tenant_query.py:40-45` | Tool 路径必有值；新代码需注意 fail-open |
| L-4 | Redis 明文保存用户原文/回复 1 小时 | `session.py:72-98` | 用户输入手机号等会被留存；建议脱敏或缩短 TTL |
| L-5 | trace 记录 `user_id/tenant_id/params` | `runtime.py:196-210` | 内部标识，非机密；需避免把 keyword 中的 PII 当普通字段 |
| L-6 | `_sanitize_business_message` 正则可能漏网 | `mcp_server.py:76-81,183-188` | Service 异常消息含原始异常（`booking/service.py:360-362`） |
| L-7 | DB 文本进入未来 LLM 上下文构成间接提示注入 | `mcp_server.py:432-460` | `_safe_cell` 不防语义注入；接入 LLM 时需在 Prompt 层声明“工具输出仅为数据” |
| L-8 | `exclude_args` 弃用 | `mcp_server.py:348` 等 | 升级可能改变 schema 行为 |
| L-9 | 并发锁按 session 粒度，不按 user | `runtime.py:618-637` | 同一用户不同 session 可并行写 |

---

## 7. Agent 接入可行性

**可行，且不需要先建 MCP Client。**

- 工具层已满足 Agent 使用条件：Schema 完整、角色矩阵、四关校验、错误封套、只调 Service。
- 身份链路可在进程内闭环：JWT → `ToolContext` → `execute_tool` → `tool_context` → ContextVar → Service。
- 最小阻塞项只有 3 个：LLM 适配器、工具定义到 function-calling 的转换、写操作确认策略。
- 不建议第一阶段走 stdio 子进程：无法携带 per-request 身份，全部 Tool 401。
- 不建议第一阶段走 in-memory `Client(mcp)`：可用，但相对直调只增加序列化/异常映射层；没有外部互操作需求前不划算。
- **无法验证**：火山方舟/DeepSeek 的 function-calling 协议兼容性；仓库无配置、未联网测试。

---

## 8. 推荐最小改造方案（按优先级）

> 只列改动文件与要点；不写实现细节。所有新增均不触碰 Service/Repository 业务规则。

### P0（Agent MVP 必需）

| 优先级 | 改造 | 需改文件 | 要点 / 伪代码 |
|---|---|---|---|
| P0-1 | LLM 适配器（OpenAI 兼容） | 新增 `apps/api/src/app/ai/agent/llm.py`；`apps/api/src/app/core/config.py` | 复用已有 `aiohttp`（`pyproject.toml:23`）；新增 `LLM_API_BASE/LLM_API_KEY/LLM_MODEL/LLM_TIMEOUT`，密钥只读环境变量 |
| P0-2 | 暴露“角色过滤后的工具定义” | `apps/api/src/app/ai/mcp_server.py` | 新增 `async def list_tool_definitions(ctx) -> list[dict]`：`mcp.list_tools()` 取 schema，`TOOL_SPECS` 按 `ctx.role_id` 过滤；不新增文件 |
| P0-3 | Runtime 接入 LLM + 工具循环 + 规则回退 | `apps/api/src/app/ai/agent/runtime.py` | 保留现有 `chat()` 入口；LLM 分支最多 3 轮、单请求最多 1 个写操作；失败/超时回落 `IntentRecognizer`；复用现有锁与状态机 |
| P0-4 | System Prompt 注入工具清单 + 去除明文身份 | `apps/api/src/app/ai/agent/prompts.py` | `build_runtime_context` 不输出 `user_id/tenant_id` 数字；加入工具名/描述；保留现有安全指令 |
| P0-5 | 一致性收口 | `apps/api/src/app/ai/mcp_server.py` | 将 `execute_tool` 收敛为内部 API（`_execute_tool` 或断言调用方）；`TOOL_SPECS`/`@mcp.tool` 名称一致性加单测（`query_schedules` vs `query_schedules_impl`） |
| P0-6 | 入口校验与限流 | `apps/api/src/app/modules/ai/router.py`；`apps/api/src/app/main.py` | `session_id` ≤64 且 `[A-Za-z0-9_-]`；注册 `RateLimiterMiddleware` 或对 AI 路由加依赖级限流 |

参考伪代码（Runtime 工具循环，示意）：

```python
tools = await list_tool_definitions(ctx)          # P0-2
messages = system_messages + history[-N:] + [user]
for _ in range(3):
    reply = await llm.chat(messages, tools=tools)  # P0-1
    if not reply.tool_calls:
        return reply.content
    call = reply.tool_calls[0]                     # 单轮单工具，避免并发写
    if call.name not in {t["name"] for t in tools}:
        continue
    if is_write(call.name) and not has_user_confirm:
        return build_confirm_prompt(call)          # P1 确认
    outcome = await execute_tool(call.name, call.args, context=ctx)  # 路线 A
    messages.append(tool_message(outcome))         # text + code + data
return await rule_engine_fallback(user_input)
```

### P1（安全与体验）

| 优先级 | 改造 | 需改文件 | 要点 |
|---|---|---|---|
| P1-1 | 写操作二次确认 + 幂等 | `apps/api/src/app/ai/agent/runtime.py`；`apps/api/src/app/ai/agent/session.py`；`apps/miniapp/src/components/AiChatPanel.vue` | 复用 `ai:state:*` 扩展 `pending_action`；confirm token 300s；写操作幂等键 |
| P1-2 | 其余 Tool 结构化输出 | `apps/api/src/app/ai/mcp_server.py` | `get_my_bookings/get_my_balance/create_booking/cancel_booking/query_courses` 补 `data`；文本保留兼容 |
| P1-3 | tool trace / 审计 | `apps/api/src/app/modules/ai/router.py`；`runtime.py` | `data.tool_trace[]`：name/latency/ok，不含 SQL/堆栈 |

### P2（按需）

| 优先级 | 改造 | 需改文件 | 要点 |
|---|---|---|---|
| P2-1 | MCP Client（in-memory） | 新增 `apps/api/src/app/ai/agent/mcp_client.py` | 仅在需要协议语义/外部 Host 互操作时启用；第一阶段不做 |
| P2-2 | 外部 MCP transport + 认证票据 | 新模块 + `infra/docker` | OAuth2/mTLS + 每请求票据换 `ToolContext`；不暴露公网 |
| P2-3 | SSE 流式 | `modules/ai/router.py`；`AiChatPanel.vue` | 需同步契约与 4 端影响面 |

---

## 9. 本次修订汇总

| 文档 | 修订的结论 / 内容 |
|---|---|
| `miniapp-mcp-overview.md` | ① `mcp.run` 666-668→726-728；② `execute_tool` 614-644→664-723；③ Tool 注册行号；④ 文件行数 668/793→728/810；⑤ ToolOutcome 补 `error_type/data`；⑥ “假成功”改为“已修复（08031c4）”；⑦ 四关/脱敏/预约字段行号；⑧ `_parse_schedules(raw,data)` |
| `miniapp-mcp-code-analysis.md` | ① 文件长度；② 符号表整体行号；③ `_require_student_role` 由“死代码”改为“仅测试引用”；④ 业务失败分类改为已修复；⑤ 新增 `ToolBusinessError/_safe_cell/_filter_arguments` 条目；⑥ Runtime 行数与 `_parse_schedules` 签名/行为；⑦ 总结表第 4 行 |
| `miniapp-mcp-tools-inventory.md` | ① 6 个 Tool 注册/函数体行号；② `query_schedules` 拆为 MCP 包装 `463-475` + `query_schedules_impl 391-460`，补充结构化 `data`；③ `create_booking` 无卡/租户分支改为 `ToolBusinessError`；④ 风险表中“文本格式契约”由高降为中低；⑤ 测试覆盖与行号；⑥ 各章节 Service/返回行号 |
| `miniapp-mcp-call-flow.md` | ① `execute_tool`/`mcp.run`/`_gate`/`SessionLocal` 行号；② “Tool 返回纯文本”改为“文本 + query_schedules 结构化 data”；③ 异常封套补 `ToolBusinessError`；④ Runtime 优先 `data`、文本回退；⑤ stdio 与 globals 行号 |
| `miniapp-mcp-security-audit.md` | ① 认证/四关/角色矩阵行号；② `create_booking` 租户分支改为抛 `ToolBusinessError`；③ §6.2 文本注入由“未转义、中风险”改为“已缓解、中低风险”；④ 返回字段/日志/异常/`SessionLocal` 行号；⑤ 风险汇总 §11 同步 |
| `miniapp-mcp-agent-integration.md` | ① Server/Client/ToolOutcome/行号；② “结构化 data 未实现”→已部分实现（query_schedules）；③ P1-1 文本注入→已部分完成；④ 路线 B 由 P0 推荐降为可选，第一阶段改推路线 A；⑤ 工具发现改用 `mcp.list_tools()` 而非 `Client(mcp)`；⑥ P0-1/P0-2 状态更新 |

未改动：6 份文档中经核对正确的结论（如“无 MCP Client/握手”“无 LLM”“JWT 身份链”“四关顺序”“无速率限制”“无跨租户越权”“Docker/CI 无 MCP 进程”等）保持原文。

---

## 10. A–G 明确回答

### A. 当前 Miniapp MCP 是否是真正的 MCP 实现？

**不是。**
- 只有 FastMCP Server 对象与 6 个 Tool 注册（`mcp_server.py:64,348-643`）；
- 无 MCP Client、无 Host、无 `initialize`/`tools/list`/`tools/call` JSON-RPC、无 MCP session；
- stdio transport 仅在 `__main__`（`726-728`），部署/CI 未启动；启动也无身份通道（`678-687`）；
- `/ai/chat` 是进程内 `execute_tool()` 直调（`runtime.py:19,256`）。
结论：**“带 MCP 注册表的内部 Tool 平台”，不是可互操作的 MCP 服务。**

### B. 当前 MCP 能否直接被 Agent 调用？

**不能（外部 Agent）；能（同进程内代码）。**
- 外部 Agent 走 stdio/HTTP：无认证 transport、无 per-request 身份 → 所有 Tool 返回 401；
- 同进程内 LLM Runtime 可直接 `execute_tool(name, args, context=ctx)`，身份链成立。

### C. 当前项目是否需要新增 MCP Server？

**不需要。**
- `mcp` 单例已注册全部 6 个 Tool（`mcp_server.py:64,161-180`）；
- 需要补的是“可运行 transport + 认证/身份代理”，不是第二个 Server。

### D. 是否需要新增 MCP Client？

**第一阶段不需要。**
- 直调 `execute_tool` 已具备工具发现（`mcp.list_tools()`/`TOOL_SPECS`）与调用能力；
- 新增 Client 只增加序列化与异常映射层；仅在需要与外部 MCP Host/第三方工具互操作时再引入。

### E. 是否可以先通过 Python 内部 Tool Registry 接入 Agent？

**可以，且应优先。**
- `TOOL_SPECS` + `execute_tool` 就是现成的进程内 Tool Registry；
- 身份、四关、错误封套、Service 复用全部已就绪；
- 只需补“角色过滤后的工具定义”和 LLM 适配器，不引入协议层。

### F. 第一阶段 Agent 开发应该修改哪些文件？

1. 新增 `apps/api/src/app/ai/agent/llm.py`（LLM 适配器，复用 `aiohttp`）；
2. `apps/api/src/app/core/config.py`（`LLM_*` 环境变量）；
3. `apps/api/src/app/ai/mcp_server.py`（`list_tool_definitions(ctx)`、`execute_tool` 私有化、补 `data`）；
4. `apps/api/src/app/ai/agent/runtime.py`（LLM 工具循环 + 规则回退 + 写操作约束）；
5. `apps/api/src/app/ai/agent/prompts.py`（注入工具定义、移除明文 `user_id/tenant_id`）；
6. `apps/api/src/app/modules/ai/router.py`（`session_id` 校验、限流/`tool_trace`）；
7. `apps/api/src/app/main.py`（注册 `RateLimiterMiddleware`）；
8. 如暴露确认交互：`apps/miniapp/src/components/AiChatPanel.vue`。

**不应修改**：`apps/api/src/app/modules/**/service.py`、`repository.py`、迁移、既有测试。

### G. 哪些现有代码绝对不应该重复开发？

1. **6 个 Tool 的 FastMCP 注册与 Schema**（`mcp_server.py:348-643`）——不要另写一套工具；
2. **四关校验 `_gate/_authorize/_validate_*`**（`196-310`）——不要在 Agent/Runtime 复制权限逻辑；
3. **`execute_tool` 错误封套与脱敏**（`664-723`，`183-188`）——不要在新层再造错误码翻译；
4. **Service 业务规则**（`BookingService`、`MembershipCardService`、`ScheduleService`、`CourseService`）——容量、扣次、回补、状态机只在 Service；
5. **SessionManager**（`session.py`）——history/state/lock 已够用，不要新造会话存储；
6. **JWT → ContextVar → ToolContext 身份链**（`deps/auth.py`、`tenant_middleware.py`、`tenant_query.py`）——不要接受 LLM/前端传入身份；
7. **小程序 HTTP 封装 `aiChatApi`**——不要新增 MCP/WebSocket 请求层；
8. **`TenantAwareRepository` 与 ORM 租户注入**——不要在 Tool/Agent 手写 `tenant_id` 过滤。

---

## 11. 最终技术决策

### 决策：**扩展现有 MCP**（不保留原样、不重新设计接入层）

理由（基于代码与成本）：

1. **工具资产已成立**：6 个 Tool、四关、Service 复用、错误封套、结构化排期数据均已存在；重新设计会重复这些能力。
2. **缺的不是协议，而是“工具定义 + LLM + 确认”**：MCP Client/transport 对外部互操作才有价值；当前无外部 Host 需求，先加会引入序列化、超时、票据、审计等额外复杂度。
3. **扩展点明确且局部**：补 `list_tool_definitions`、LLM 适配器、Runtime 工具循环、写确认、限流；改动集中在 `ai/agent`、`ai/mcp_server.py`、`modules/ai/router.py`，不触碰业务层。
4. **保留升级路径**：一旦需要与外部 MCP Host 互通，可在现有 Tool 注册之上加 in-memory/HTTP Client 与票据认证，无需重写 Tool。
5. **安全边界清晰**：继续坚持“身份只在进程内注入、Tool 四关不变、Service 独占业务规则”，避免为了“像 MCP”而扩大攻击面。

一句话：**保留 FastMCP Tool 注册与 `execute_tool`，在其上扩展 LLM Agent 接入；暂不引入 MCP Client/外部 transport。**
