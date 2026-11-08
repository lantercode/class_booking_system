# 小程序 AI 助手 / MCP 现状审计（二）代码逐文件分析

> 审计性质：只读。未修改任何业务代码、配置、迁移或测试。
> 分析对象：`apps/api/src/app/ai/` 全部文件、`apps/api/src/app/modules/ai/router.py`、`apps/miniapp` AI 消费端、AI/MCP 相关测试。
> 行号均来自本次实际读取；文件长度以 `wc -l` 实测为准。
> **已按交叉验证修订（依据：`apps/api/src/app/ai/mcp_server.py:99-106,161-180,391-475,664-723,726-728`、`agent/runtime.py:700-755`，commit `08031c4`）**。修订明细见 `miniapp-mcp-validation-report.md` §1/§9。

---

## 1. `apps/api/src/app/ai/mcp_server.py`（728 行）

### 1.1 职责

- 创建唯一 `FastMCP` 实例（`mcp_server.py:64`）。
- 声明 Tool 元数据 `ToolSpec / TOOL_SPECS`（`149-180`）。
- 实现四关校验：`_gate` / `_authorize` / 租户归属 / 入参校验（`196-310`）。
- 实现 6 个 `@mcp.tool` 函数（`348-643`）。
- 提供统一执行入口 `execute_tool`（`664-723`）与 stdio 启动分支（`726-728`）。

### 1.2 依赖

| 类型 | 依赖 | 行号 |
|------|------|------|
| 第三方 | `fastmcp.FastMCP` | `45` |
| 基础设施 | `app.core.database.SessionLocal` | `47` |
| 异常 | `BusinessException, DanceSaasException` | `48` |
| RBAC | `get_user_role_codes` | `49` |
| 租户 | `get_tenant_id` / `tenant_id` / `user_id` ContextVar | `50-52` |
| 领域 | `BookingStatus`、`BookingCreate`、`BookingService` | `53-55` |
| 领域 | `CourseService`、`MembershipCardService`、`ScheduleService`、`UserService` | `56-59` |

> 依赖层面**没有** Repository / 裸 SQL / Redis；符合 `ai/mcp.md` 的“Tool 只能调 Service”。

### 1.3 结构与关键函数

| 区块 | 行号 | 说明 |
|------|------|------|
| `GENERIC_ERROR_TEXT` / `LOGIN_REQUIRED_TEXT` | `70-71` | 统一兜底文案 |
| `_INTERNAL_PATTERN` | `76-81` | 用于拦截 SQL / traceback / 密钥等内部特征 |
| `ToolOutcome` | `84-96` | `kind ∈ success/business_error/validation_error/system_error`；含 `text/code/error_type/data`，`ok` 属性 |
| `ToolBusinessError` | `99-106` | Tool 层业务失败异常，携带 `message/code/error_type` |
| `ToolContext` | `109-116` | 可信身份：`user_id/tenant_id/role_id` |
| `_tool_ctx` ContextVar | `118` | 进程内可信上下文 |
| `tool_context()` | `126-141` | 绑定/复位 `_tool_ctx`、租户、用户 ContextVar |
| `ToolSpec` | `149-155` | `name/handler_name/required_roles/is_write/input_fields` |
| `_READ_ROLES` / `_STUDENT_ONLY` | `158-159` | 角色集合 |
| `TOOL_SPECS` | `161-180` | 6 个 Tool 的单一元数据源 |
| `_sanitize_business_message` | `183-188` | 长度 >200 或命中内部特征 → 统一兜底 |
| `_authorize` | `196-209` | 调 `get_user_role_codes`，角色交集判定 |
| `_gate` | `212-250` | 认证 → 授权 → 租户 →（入参由各 Tool 继续） |
| `_invalid_positive_int` | `253-254` | 排除 bool / 非 int / ≤0 |
| `_validate_id / _validate_text / _validate_enum` | `257-285` | 入参校验 |
| `_parse_date` | `288-302` | 严格 `YYYY-MM-DD`，范围：today-30 ~ today+90 |
| `_validate_days` | `305-310` | 默认 7，范围 1-30 |
| `_require_student_role` | `313-322` | 仅被测试引用（`tests/test_mcp_tool_authorization.py:20,165,225`），业务代码无调用 |
| 状态/枚举映射 | `329-345` | `STATUS_LABELS`、课程分类/等级、预约状态 |
| `_safe_cell` | `651-656` | 表格单元格转义：替换 `|`、压缩换行与控制字符 |
| `_filter_arguments` | `659-661` | 仅保留 `spec.input_fields`，丢弃 `user_id/tenant_id` |
| `execute_tool` | `664-723` | 过滤参数 → 绑定上下文 → 调 handler → 错误封套 |
| stdio 入口 | `726-728` | 仅 `__main__` |

### 1.4 关键实现细节

1. **身份注入**：`execute_tool` 先取 `context or _tool_ctx.get()`（`678`）；无上下文直接返回 401（`679-683`）；`user_id/tenant_id` 非法再返回 401（`684-687`）。随后 `with tool_context(ctx)`（`692`）同步 3 个 ContextVar，再以 `handler(**args, user_id=ctx.user_id, tenant_id=ctx.tenant_id)` 调用（`694`）。
2. **参数过滤**：`_filter_arguments` 只保留 `spec.input_fields`（`659-661`），因此即使调用方传 `user_id`，也不会作为业务参数透传；身份字段由 `execute_tool` 强制注入。
3. **异常封套**：`ToolBusinessError` → `business_error` + 脱敏文本（`698-705`）；`DanceSaasException` → `business_error` + 脱敏文本（`706-713`）；其他异常 → `system_error` + 统一兜底（`714-723`），内部细节只进日志。
4. **四关顺序**：认证（`224-233`）→ 显式身份一致性（`236-239`）→ 授权（`242`）→ ContextVar 租户比对（`245-246`）→ `UserService.is_user_in_tenant`（`247-248`）。入参校验在各 Tool 内 `_gate` 之后执行。
5. **租户隔离**：依赖 `ToolContext` 注入的 tenant ContextVar + `TenantAwareRepository` 自动过滤 + `is_user_in_tenant` 显式比对，形成三层防护。

### 1.5 被谁调用

| 调用方 | 方式 | 行号 |
|--------|------|------|
| `AgentRuntime._call_tool` | `execute_tool(...)` | `runtime.py:246-260` |
| 测试 | 直接 `execute_tool(...)` / 直接调用 Tool 函数 | `tests/unit/test_ai_p1_tool_platform.py`、`tests/test_mcp_tool_authorization.py` |
| 外部 MCP 客户端 | 仅当以 `__main__` 启动；仓库无配置 | `mcp_server.py:726-728` |

### 1.6 问题与状态

| 问题 | 证据 | 状态 |
|------|------|------|
| `_require_student_role` 业务代码无调用，仅测试引用 | `313-322`；`tests/test_mcp_tool_authorization.py:20,165,225` | 近似死代码（测试专用） |
| `exclude_args` 在 fastmcp 3.4.7 已标记废弃（导入时出现 DeprecationWarning） | 实测 `uv run python` 输出；`348,463,478,526,553,615` 均使用 | 风险（未经验证长期支持） |
| 业务失败以字符串返回，被包成 `success` | **已修复（08031c4）**：改为 `raise ToolBusinessError`（`581,588-592`），`execute_tool` 映射为 `business_error`（`698-705`） | 已实现 |
| 授权仅按角色 code，不校验具体权限点 | `196-209` | 设计口径；是否符合 `security/authorization.md` 需安全审计确认 |
| `role_id` 在 `ToolContext` 中未参与授权逻辑 | `109-116`、`196-209` | 冗余字段 |
| `ToolOutcome` 无 `trace_id` / `tool_name` 字段 | `84-96`（现有 `data/error_type`） | 可观测性受限 |

---

## 2. `apps/api/src/app/ai/agent/runtime.py`（810 行）

### 2.1 职责

对话编排：并发锁 → 中间状态 → 意图识别 → Tool 调度 → 文案格式化 → 会话落库 → 结构化 trace。

### 2.2 依赖

| 类型 | 依赖 | 行号 |
|------|------|------|
| 内部 | `IntentRecognizer` | `16` |
| 内部 | `prompts.build_system_messages as compose_system_messages` | `17` |
| 内部 | `SessionManager` | `18` |
| 内部 | `ToolContext/ToolOutcome/execute_tool` | `19` |
| 异常 | `BusinessException` | `20` |
| 标准库 | `hashlib/json/logging/time` | `11-14` |

### 2.3 关键结构与函数

| 结构 | 行号 | 说明 |
|------|------|------|
| `INTENT_TOOL_MAP` | `23-30` | 意图 → Tool 映射；`create_booking` 映射到 `query_schedules + create_booking` |
| `__init__` | `45-59` | 保存身份、创建 `SessionManager`；`system_messages` 仅日志用 |
| `build_system_messages` | `65-75` | 组装 2 条 system message；**不发给任何模型** |
| `_system_prompt_meta` | `77-84` | 仅长度 + SHA-256 前 12 位 |
| `chat` | `86-181` | 主流程 |
| `_new_trace / _emit_trace / _elapsed_ms / _mark_error` | `196-230` | 结构化日志 trace |
| `_tool_context` | `232-244` | `user_id/tenant_id/role_id` → `ToolContext`；缺失返回 None |
| `_call_tool` | `246-260` | 调 `execute_tool`，记录 tool 名与耗时 |
| `_handle_outcome` | `262-271` | 成功用 formatter，失败返回脱敏文本 |
| `_execute_intent` | `273-413` | 意图分支 |
| `_handle_pending_state` | `415-573` | 选排期 / 确认取消 |
| `_handle_business_error` | `579-612` | 关键词 → 友好文案 |
| `_acquire_lock / _release_lock` | `618-664` | Redis `SET NX EX` + Lua 原子释放 |
| `_handle_unknown` | `670-680` | 兜底帮助 |
| `_format_*` | `682-698` | 文案前缀 |
| `_parse_schedules` | `700-755` | 优先用 `ToolOutcome.data`，缺失时回退解析 Tool 文本 |
| `_format_schedule_options` | `757-770` | 数字选项 |
| `_parse_user_selection` | `772-810` | 支持阿拉伯数字与中文数字 |

### 2.4 主流程细节

1. **无 LLM**：`chat()` 每次组装 system messages（`101`）并只记录指纹（`102`）；源码注释明确“当前无真实 LLM 调用点”（`57,100`）。
2. **并发控制**：锁 key 为 `ai:lock:user_{id}:{session}`（`session.py:54-57`）；Redis 不存在时 `_acquire_lock` 返回 True（`631-632`）；异常也返回 True（`634-637`）。
3. **多轮状态**：先读 `get_state`（`119`）；存在则进入 `_handle_pending_state`，**不再做意图识别**。
4. **意图 → Tool**：
   - `query_courses` → 只传 `keyword`（`291-298`），不传 `category/level`。
   - `query_schedules` → 只传 `date/keyword`（`300-307`），不传 `days`。
   - `get_my_bookings` → 只传 `status`（`309-315`），不传 `upcoming`。
   - `get_my_balance` → 空参（`318-325`）。
   - `create_booking` → 只传 `schedule_id`（`368-373`、`454-459`），不传 `membership_card_id`。
   - `cancel_booking` → 只传 `booking_id`（`513-518`），不传 `reason`。
5. **预约选择流程**：意图阶段没有 `schedule_id`（`intent.py` 不提取该参数），因此 `340` 分支恒成立 → 查排期 → 存状态 `selecting_schedule`（`356-366`）→ 用户回复数字 → `_parse_user_selection` → 调 `create_booking`（`453-470`）。
6. **取消确认流程**：先存 `confirming_cancel`（`384-389`），用户回“是/确认”后执行（`512-541`）。
7. **文案重复**：多轮预约成功后由 Runtime 自己拼“预约成功 / 课程 / 时间 / 老师 / 详情”（`479-486`），与 Tool 返回文本重复；取消同理（`538-541`）。`business_error` 分支直接返回 `outcome.text`（`453-470`），不再追加成功模板。

### 2.5 问题与状态

| 问题 | 证据 | 状态 |
|------|------|------|
| “预约成功”可能为假成功 | **已修复（08031c4）**：无卡/排期不存在时 `create_booking` 抛 `ToolBusinessError`（`mcp_server.py:581,588-592`），`outcome.ok=False`，Runtime 返回失败文案（`runtime.py:453-470`） | 已实现 |
| 预约/取消结果中课程名为空 | Tool 文本“课程：None”来自 Service `_to_response` 无 schedule_info；Runtime 原样展示 `outcome.text`（`484`、`540`） | **部分实现** |
| `params["upcoming"]` 从未被消费 | `intent.py:145-146` 写入；`runtime.py:309-315` 未传 | 死参数 |
| `query_courses` 的 category/level、`query_schedules` 的 days、create 的 card 均无法从对话触发 | `291-298,300-307,368-373` | 能力未暴露 |
| 错误兜底为关键词匹配，覆盖有限 | `590-612` | 部分实现 |
| Redis 不可用时无锁 + 无历史 | `session.py:61-62,74-75`；`runtime.py:631-637` | 降级口径（可接受但需知悉） |
| `create_booking` 失败时清状态，用户需重新开始 | `461-470` | 产品体验风险 |
| `_format_cancel_result` 未使用 | `697-698`；取消分支直接拼文本 | 死代码 |

---

## 3. `apps/api/src/app/ai/agent/intent.py`（217 行）

### 3.1 职责

纯规则意图识别：关键词命中 → 意图；正则/词表 → 参数。无模型、无向量、无历史上下文。

### 3.2 关键结构

| 结构 | 行号 | 说明 |
|------|------|------|
| `INTENTS` | `25-43` | 优先级从高到低：取消 → 余额 → 我的预约 → 预约 → 卡规则 → 排期 → 课程 |
| `INTENT_DESCRIPTIONS / EXAMPLES` | `46-64` | 供 `GET /ai/intents` 枚举 |
| `UPCOMING_KEYWORDS` | `66-67` | 写入 `params.upcoming` |
| `DATE_PATTERNS` | `70-74` | 今天/明天/后天 |
| `recognize` | `80-114` | 主入口 |
| `_match_intent` | `116-127` | “可以预约/可以约/可预约”先行判为查询排期 |
| `_extract_params` | `129-153` | 按意图提取 |
| `_extract_course_keyword` | `155-161` | 固定 8 个舞种关键词 |
| `_extract_date` | `163-177` | 相对日期 + `YYYY-MM-DD` 正则 |
| `_extract_booking_status` | `179-187` | 已完成/已取消/未到 |
| `_extract_booking_id` | `189-194` | `(\d{3,})` 取第一个 ≥3 位数字 |
| `list_intents` | `200-217` | 只读枚举 |

### 3.3 能力与限制

| 项 | 结论 | 依据 |
|----|------|------|
| 支持意图 | 7 类（含 `card_rule`） | `25-43` |
| LLM 语义理解 | 无 | 文件头注释 `5-6` |
| 课程分类/等级参数 | 不提取 | `129-153` 中无 `category/level` |
| 查询天数 `days` | 不提取 | 同上 |
| 会员卡 ID | 不提取 | 同上 |
| 取消原因 `reason` | 不提取 | 同上 |
| `schedule_id` | 永不提取 | `129-153`；Runtime `340` 分支恒成立 |
| `upcoming` | 提取但下游丢弃 | `143-146`；`runtime.py:309-315` |
| 关键词歧义 | “预约”动作词优先级低于“取消/余额/我的预约”，高于“排期/课程”；`_match_intent` 内部按列表顺序先命中即返回 | `116-127` |
| 数字取 ID 误判 | 任意 ≥3 位数字都会作为 booking_id（如“取消 2026 年…”可能误判） | `189-194` |
| 状态 | **已实现**（规则口径），语义覆盖为**部分实现** | — |

### 3.4 被谁调用

`AgentRuntime.chat`（`runtime.py:140`）、`GET /api/v1/ai/intents`（`modules/ai/router.py:110-119`）、单元测试（`tests/unit/test_ai_p0_stability.py:201-221`）。

---

## 4. `apps/api/src/app/ai/agent/session.py`（155 行）

### 4.1 职责

Redis 会话历史、中间状态、并发锁 key 生成与读写；`user_id + session_id` 双层隔离。

### 4.2 关键实现

| 项 | 行号 | 说明 |
|----|------|------|
| key 规范 | `22-31` | `ai:session:{user_id}:{session}` / `ai:state:...` / `ai:lock:...` |
| `_session_scope_key` | `39-47` | 未登录用户退化为 `anon` |
| `_state_scope_key` | `49-52` | 同上 |
| `_lock_scope_key` | `54-57` | 同上 |
| `get_history / add_message` | `59-98` | 历史 JSON；`max_history=10` → 最多 20 条；TTL 3600s |
| `clear` | `100-106` | 删除历史 |
| `get_context` | `108-117` | 最近 N 条拼文本（**当前无调用方**） |
| `set_state / get_state / clear_state` | `119-155` | 状态 TTL 600s |
| 异常处理 | `64-70,77-98,102-106,124-134,141-147` | 全部吞异常 + 日志，不影响主流程 |

### 4.3 状态与风险

| 项 | 结论 |
|----|------|
| Redis 不可用时 | 历史为空、状态为空、锁视为成功（`61-62,74-75,124-125`） |
| 历史是否参与意图 | 否；仅落库供 `/history` 展示 |
| 跨用户隔离 | **已实现**（key 含 user_id） |
| `get_context` | **未实现使用**（死代码） |
| 状态序列化 | JSON 存储，含排期列表，存在 Redis 体积风险（≤10 项，可接受） |

---

## 5. `apps/api/src/app/ai/agent/prompts.py`（82 行）

### 5.1 职责

定义 System Prompt 与运行约束文本，供未来 LLM 适配层复用。

### 5.2 关键点

| 项 | 行号 | 说明 |
|----|------|------|
| 文件说明 | `5-8` | 明确“当前未接入真实 LLM”“禁止回传前端” |
| `SYSTEM_PROMPT` | `13-34` | 角色、安全规则（防注入、不泄露、写操作需确认） |
| `build_runtime_context` | `37-56` | 注入 user_id/tenant_id/role_id 与可用 Tool 清单 |
| `build_system_messages` | `59-82` | 返回 2 条 system message |
| 被谁调用 | `runtime.py:70-75` → `build_system_messages` | 仅用于日志 |

### 5.3 状态

Prompt 内容：**已实现**（含防注入/不泄露/写操作确认）；真实模型注入：**未实现**（无 LLM 客户端）；回传前端：**未实现**（仅记录指纹）。

---

## 6. `apps/api/src/app/ai/rag/retriever.py`（42 行）

| 项 | 内容 |
|----|------|
| 职责 | 名义上从 Milvus 检索 FAQ |
| 实现 | `search()` 直接返回 1 条硬编码 FAQ（`36-42`） |
| TODO / 依赖 | `30-33` 注释说明向量化/检索未接；构造参数 `embedder/milvus_client` 可注入（`14-18`） |
| 被谁调用 | **全仓无调用**（`grep Retriever` 仅定义处） |
| 状态 | **未实现**（stub）；风险：若被接入会把假数据当真实知识 |

---

## 7. `apps/api/src/app/ai/rag/embedder.py`（38 行）

| 项 | 内容 |
|----|------|
| 职责 / 实现 | 名义 OpenAI `text-embedding-3-small` 1536 维；`embed()` 实际返回 `[[0.0] * 1536]`（`38`） |
| TODO | `29-35` 注释掉的 OpenAI 调用 |
| 依赖 | 仅 `api_key` 参数；无 `openai` 实际导入 |
| 被谁调用 | 无 |
| 状态 | **未实现**（stub） |

---

## 8. `apps/api/src/app/modules/ai/router.py`（119 行）

### 8.1 路由与依赖

| 端点 | 方法 | 认证 | 行号 | 说明 |
|------|------|------|------|------|
| `/api/v1/ai/chat` | POST | `Depends(get_agent_runtime)` → `get_current_user` | `59-81` | `message` 1-500 字符；`session_id` 默认 `default` |
| `/api/v1/ai/history` | GET | 同上 | `84-99` | 返回最近 50 条 |
| `/api/v1/ai/history` | DELETE | 同上 | `102-107` | 清空 |
| `/api/v1/ai/intents` | GET | `Depends(get_current_user)` | `110-119` | 调试枚举 |

### 8.2 身份注入

`get_agent_runtime` 从 `current_user` 取 `user_id/tenant_id/role_id`（`47-56`），不接收请求体身份字段；符合 `ai/ai-architecture.md`。

### 8.3 问题

| 问题 | 证据 | 状态 |
|------|------|------|
| 文档声称“请求限流（防刷）”但无实现 | `5`；无 `@rate_limit`；`main.py:207-213` 只定义配置；全仓无 `add_middleware(RateLimiter...)` 实际调用 | **未实现** |
| 无 RBAC 装饰器 | 对比写操作端点要求；AI 端点仅依赖登录态 | 需安全审计判定 |
| `/chat` 无工具执行 trace 返回 | `71-81` 只返回 response/session/timestamp/pending/latency | 契约限制 |
| `GET /intents` 的 `current_user` 未使用 | `110-119` | 冗余依赖 |
| 不在 `packages/api-client` | `packages/api-client/src` 文件清单无 ai.ts | 小程序自建请求封装 |

### 8.4 被谁调用

- `main.py:230` `app.include_router(ai_router)`（`ai_router` 自带前缀 `/api/v1/ai`）。
- 小程序 `aiChatApi`（`apps/miniapp/src/api/index.ts:735-754`）。

---

## 9. 小程序消费端代码分析

### 9.1 `apps/miniapp/src/api/index.ts`（869 行）

| 项 | 行号 | 说明 |
|----|------|------|
| `AiChatMessage` | `80-85` | `role: user/assistant` |
| `AiChatResult` | `87-94` | `response/session_id/timestamp/has_pending_state/latency_ms` |
| `aiChatApi.chat` | `735-744` | `POST /ai/chat`，第 5 参 `showError=false` |
| `aiChatApi.getHistory` | `746-749` | `GET /ai/history` |
| `aiChatApi.clearHistory` | `751-753` | `DELETE /ai/history`，body 传 `session_id` |
| `request()` | `219-269` | `uni.request`；自动带 `Authorization` + `x-tenant-slug`；401 refresh |
| BASE_URL | 文件上部 | 小程序必须用绝对地址（无同源能力） |

> 结论：**纯 HTTP 客户端**；无 MCP SDK 依赖，无 JSON-RPC，无 `initialize/tools/list/tools/call`。

### 9.2 `apps/miniapp/src/components/AiChatPanel.vue`（703 行）

| 项 | 行号 | 说明 |
|----|------|------|
| `aiChatApi` 导入 | `135` | 唯一数据通道 |
| props | `146-162` | `sessionId/theme/showClear/autoRestoreHistory` |
| 快捷问题 | `185-190` | 4 条固定文案 |
| `buildSessionId` | `192-198` | 优先 props；否则 `session_{userInfo.id}` |
| `currentSessionId` | `200` | setup 时一次性取值 |
| `loadHistory` | `219-233` | 教师端弹窗默认恢复 |
| `doSend` | `235-279` | push 用户消息 → `aiChatApi.chat` → push assistant 消息 |
| `has_pending_state` | `248-258` | **未读取**；只看 `res.data.response` |
| 错误处理 | `267-274` | 网络错误提示 |
| `clearHistory` | `312-328` | 二次确认后调接口 |

### 9.3 `apps/miniapp/src/pages/student/ai-assistant/index.vue`（118 行）

| 项 | 行号 | 说明 |
|----|------|------|
| 页面结构 | `2-26` | 顶部栏 + `AiChatPanel` + TabBar |
| sessionId | `45-47` | `student_{userId||default}_{entryTs}`；`userId` 在 `onMounted` 才赋值（`49-54`） |
| 登录校验 | `50` | `checkLogin("student")` |
| `autoRestoreHistory` | `21` | 学员整页每次进入空会话 |

### 9.4 教师端

`pages/teacher/profile/index.vue:68` 使用 `<AiAssistant :session-id="'teacher_' + (userId || 'default')" />`；`AiAssistant.vue:21-46` 为弹窗壳，内部复用 `AiChatPanel`（`43-46`），会话恢复默认开启（`AiChatPanel.vue:160`）。

---

## 10. 测试分析

| 测试文件 | 覆盖点 | 未覆盖/局限 |
|----------|--------|-------------|
| `tests/test_mcp_tool_authorization.py` | 写操作 401/403/400；`_validate_id`；直接调用 Tool + `tool_context`（`18-40`） | 仅 create/cancel；monkeypatch `is_user_in_tenant` |
| `tests/unit/test_ai_p1_tool_platform.py` | `execute_tool` 四关、错误封套、`TOOL_SPECS` 6 项齐全（`328-339`）、create DTO 契约 | 未覆盖真实 Service 返回的 `course_name=None` |
| `tests/unit/test_ai_p0_stability.py` | 意图关键词（`201-215`）、card_rule 不调 Tool（`218-224`）、history ISO 时间戳 | 未覆盖 HTTP 路由 |
| `tests/test_agent_runtime.py` | Runtime 编排、`_parse_schedules` 文本契约（`108-110`）、monkeypatch Tool | 未覆盖真实 DB |
| `tests/test_multi_turn_booking.py` | 选排期、取消确认 | 未覆盖无卡失败文案 |
| `tests/test_exception_handlers.py` | 仅用 `/ai/chat` 作为 request path 示例（`80`） | 非 AI 功能测试 |

> **未经验证**：没有任何测试通过 `AsyncClient` 调用真实 `POST /api/v1/ai/chat`；HTTP 端到端行为无自动化证据。

---

## 11. 跨文件发现汇总

| # | 发现 | 涉及文件:行号 | 状态 |
|---|------|---------------|------|
| 1 | `/ai/chat` 不走 MCP 协议，走进程内 `execute_tool` | `runtime.py:19,256`；`mcp_server.py:664-723` | 已实现 |
| 2 | 无 LLM，规则引擎决定意图 | `intent.py:5-6,116-127`；`prompts.py:5-8` | 已实现（无 LLM） |
| 3 | Tool 注册有 6 个，Schema 排除身份字段 | `mcp_server.py:348-643`；实测 Schema | 已实现 |
| 4 | `create_booking` 无卡/排期不存在曾被当成功 | **已修复（08031c4）**：`raise ToolBusinessError`（`mcp_server.py:581,588-592`）→ `business_error`（`698-705`） | 已实现 |
| 5 | 预约/取消结果课程名为 `None` | `booking/service.py:252,368,1513`；`mcp_server.py:606-612,637-643` | 缺陷 |
| 6 | `upcoming` 死参数 | `intent.py:145`；`runtime.py:309-315` | 部分实现 |
| 7 | 限流声明未实现 | `modules/ai/router.py:5`；`main.py:207-213` | 未实现 |
| 8 | 小程序忽略 `has_pending_state` | `api/index.ts:88-94`；`AiChatPanel.vue:248-258` | 部分实现 |
| 9 | RAG 为假数据 | `retriever.py:36-42`；`embedder.py:38` | 未实现 |
| 10 | `_require_student_role`（仅测试引用）、`get_context`、`_format_cancel_result` 死代码 | `mcp_server.py:313-322`；`session.py:108-117`；`runtime.py:697-698` | 清理项 |

---

## 12. 未经验证清单

| 项 | 原因 |
|----|------|
| FastMCP 3.4.7 `exclude_args` 的未来兼容性 | 仅观察到 deprecation warning；未升级依赖验证 |
| 外部 MCP 客户端是否存在并实际调用 | 仓库无 MCP 配置；未进行外部环境排查 |
| 小程序 `sessionId` 中 `userId` 是否真为预期值 | `AiChatPanel.vue:200` setup 时取值 vs 页面 `onMounted` 赋值（`index.vue:49-54`），需真机验证 |
| `/ai/chat` 在真实 Redis / DB 下端到端 | 本次未启动服务 |
| 真实数据下 Tool 文本长度是否触发 `_sanitize` 200 字符阈值 | 需真实业务数据 |
| 写操作 Tool 在 MCP stdio 外部客户端下的行为 | 代码设计为 401 拒绝，但无真实客户端调用复现 |
