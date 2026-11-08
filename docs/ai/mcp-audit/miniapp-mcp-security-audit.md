# 小程序 AI 助手 / MCP Tool 安全审计

> 审计对象：`apps/miniapp` AI 面板 + `POST /api/v1/ai/chat` + `apps/api/src/app/ai/mcp_server.py` 六个 Tool
> 方式：只读代码审计；不修改代码、不运行业务写操作
> 审计时间：2026-11-06
> 风险等级：**高 / 中 / 低**；状态：**已实现 / 部分实现 / 未实现 / 未经验证**
> **已按交叉验证修订（依据：`apps/api/src/app/ai/mcp_server.py:99-106,391-475,651-656,664-723,726-728`、`agent/runtime.py:700-755`，commit `08031c4`）**。修订明细见 `miniapp-mcp-validation-report.md` §1/§9。

---

## 1. 审计范围与信任边界

| 层 | 组件 | 是否对外暴露 |
|---|---|---|
| 客户端 | 微信小程序 `AiChatPanel.vue` → `aiChatApi` | 是（用户设备） |
| HTTP 入口 | `POST/GET/DELETE /api/v1/ai/*` | 是（需登录 + 租户头） |
| 应用层 | `AgentRuntime` + `IntentRecognizer` + `SessionManager` | 否（进程内） |
| Tool 层 | `execute_tool` + 6 个 Tool 函数 | 否（当前无 MCP RPC 暴露） |
| Service / Repository / DB | 业务规则与数据 | 否 |

**核心信任假设**：Tool 身份只来自 HTTP 层 `get_current_user` 的 JWT payload，经 `AgentRuntime` 构造 `ToolContext` 注入；LLM/前端/消息体**不得**提供身份。当前一切成立的前提是“Tool 只在 API 进程内被调用”，因为不存在 MCP RPC 入口（见调用链文档 §7）。

---

## 2. 认证链路（JWT → ContextVar → ToolContext）

```
Authorization: Bearer <access_token>
  → get_current_user (deps/auth.py:40-66)
      - 必须 Bearer 前缀 (46-50)
      - decode_token HS256 (54)
      - Redis 黑名单 blacklist:<jti> (59-60)
      - set_tenant_id / set_user_id / set_role_id (62-64)
  → router.get_agent_runtime (modules/ai/router.py:47-56)
      - user_id = current_user["user_id"]
      - tenant_id = current_user["tenant_id"]
      - role_id = current_user["role_id"]
  → AgentRuntime.__init__ (runtime.py:45-59)
  → _tool_context() (runtime.py:232-244)  // 缺失则 None
  → execute_tool(..., context) (mcp_server.py:664-723)
  → tool_context(ctx) 同步 ContextVar (mcp_server.py:126-141)
  → _gate 第一关 (mcp_server.py:224-233)
```

结论：**已实现**。
- 前端请求体无身份字段：`ChatRequest` 只有 `message/session_id`（`modules/ai/router.py:30-32`）；小程序也只发这两个字段（`apps/miniapp/src/api/index.ts:740`）。
- 未认证请求在 `Depends(get_current_user)` 层即 401，不会进入 Runtime（`router.py:47-50`）。
- 中间件层的 `x-tenant-slug` 只决定“能进哪个租户的入口”；真正用于 Tool 的租户来自 JWT（`auth.py:62` 在中间件 `set_tenant_id` 之后再次覆盖）。

---

## 3. 四关校验实现对照

> 规范要求顺序：Authentication → Authorization → Tenant Validation → Input Validation（`.trae/rules/ai/mcp.md`）

| 关卡 | 实现位置 | 实际内容 | 状态 |
|---|---|---|---|
| Authentication | `mcp_server.py:224-233` + `execute_tool:678-687` | `_tool_ctx` 必须存在；user_id/tenant_id 必须为正整数；旧式显式 `user_id/tenant_id` 只允许与可信上下文一致，否则 403 | 已实现 |
| Authorization | `mcp_server.py:196-209`；`core/rbac/checker.py:406-453` | 查 `user_roles JOIN roles`（本租户角色 + 全局角色），与 `ToolSpec.required_roles` 求交；查库异常返回空集合 → **fail closed** | 已实现 |
| Tenant Validation | `mcp_server.py:236-248`；`modules/user/service.py:519-531` | ① `get_tenant_id() == ctx.tenant_id` 显式比对；② `is_user_in_tenant()` 校验用户归属；③ Repository/ORM 自动注入（第三层） | 已实现 |
| Input Validation | `mcp_server.py:253-310` + 各 Tool 内调用 | ID 正整数（拒绝 bool/str/0/负数）；文本长度（关键词 50、原因 200）；枚举白名单；日期 `YYYY-MM-DD` 且范围 [-30, +90] 天；days 1–30 | 已实现 |

补充：
- `_filter_arguments()` 只保留 `ToolSpec.input_fields`（`mcp_server.py:659-661`），**身份字段即使被模型/调用方传入也会被丢弃**；Tool 内部再显式拒绝不一致身份（`236-239`）。
- FastMCP 注册 schema 已 `exclude_args=["user_id","tenant_id"]`（本次实测 `mcp.list_tools()` 属性不含身份字段），外部客户端连 schema 都看不到身份参数。
- `get_user_role_codes` 异常时返回 `set()`（`checker.py:455-457`），`_authorize` 会拒绝（`mcp_server.py:203-209`）→ 授权失败安全默认。

---

## 4. RBAC 与“能否绕过”

### 4.1 角色矩阵（`mcp_server.py:158-180`）

| Tool | 允许角色 | 写操作 |
|---|---|---|
| `query_courses` | student / teacher / admin / super_admin | 否 |
| `query_schedules` | student / teacher / admin / super_admin | 否 |
| `get_my_bookings` | student / teacher / admin / super_admin（但强制 `self_only=True`） | 否 |
| `get_my_balance` | 仅 student | 否 |
| `create_booking` | 仅 student | 是 |
| `cancel_booking` | 仅 student | 是 |

### 4.2 是否依赖全局 bypass？

- `PERMISSION_CHECK_BYPASS` 定义于 `apps/api/src/app/core/config.py:57`，判定逻辑在 `core/rbac/checker.py:45`。
- Tool 授权**不调用**该开关：`_authorize` 直接查 `get_user_role_codes`（`mcp_server.py:196-209`）。全仓 grep 显示 `mcp_server.py:199` 仅有一句“不使用 PERMISSION_CHECK_BYPASS”的注释。
- 结论：**工具授权不受 bypass 影响（已实现）**。

### 4.3 是否可能绕过 RBAC？

针对当前 HTTP 链路：**不能**。
- Tool 只能通过 `execute_tool` 进入，且 `_gate` 每 Tool 必调；
- `execute_tool(context=...)` 的 `context` 参数是进程内 API，但全仓只有 `AgentRuntime._call_tool` 构造 `ToolContext`（grep 结果：`runtime.py:240,256`），没有任何 HTTP 端点从请求体构造它；
- `/ai/chat` 本身没有 `@require_permissions`（`modules/ai/router.py:59`），但它只操作“本人数据”（`self_only`）或“租户公开数据”，不涉及管理类动作，符合最小权限。
- 残余风险：**若未来新增 HTTP 端点或 MCP RPC 直接调用 `execute_tool` 并允许外部传入 `ToolContext`，即可绕过全部四关**。这属于必须用代码评审守住的边界，风险等级：**中**（当前不可利用）。

### 4.4 MCP Server 自身的访问控制

| 检查项 | 结论 | 依据 |
|---|---|---|
| 是否有独立监听端口 | **没有**。FastMCP 对象只在 API 进程内创建，未调用 `run()` 监听 | `mcp_server.py:64,726-728` |
| 是否有 stdio transport 在跑 | **没有**。`mcp.run(transport="stdio")` 仅位于 `if __name__ == "__main__"`，部署与 CI 均未启动该模块 | `mcp_server.py:726-728`；`apps/api/Dockerfile:29`；`docker-compose.prod.yml:2-61`；`.github/workflows/ci.yml:66,86` |
| 外部可达入口 | 仅 HTTP `/api/v1/ai/*`，受 JWT + 租户中间件保护 | `modules/ai/router.py:47-56`；`deps/auth.py:40-66` |
| Server 侧网络 ACL / mTLS | **未实现（也不需要，因为无网络面）** | 同上 |

结论：当前“MCP Server”是**进程内库**而非网络服务，访问控制完全由 HTTP 层承担；一旦未来改为独立进程/HTTP transport，必须在 Server 侧补认证（见 §11）。


---

## 5. 多租户隔离审计

### 5.1 三层隔离现状

| 层 | 实现 | 对 AI 链路是否生效 |
|---|---|---|
| Middleware | `TenantASGIMiddleware`（`tenant_middleware.py:41-103`） | 生效：`/api/v1/ai/*` 不在跳过白名单（`24-38`），无租户头直接 400（`80-92`） |
| ContextVar | `tenant_context.py:3,38-45`；中间件写一次、`get_current_user` 用 JWT 覆盖（`auth.py:62`）、`tool_context` 再写一次（`mcp_server.py:134`） | 生效 |
| ORM 自动过滤 | `tenant_query.py:29-80`，lifespan 注册（`main.py:62`） | 生效：仅当 ContextVar 有值；Tool 内 `tool_context` 已保证有值 |

### 5.2 Tool 内的租户防线（不止一层）

1. `_gate` 显式比对 `get_tenant_id() != ctx.tenant_id` → 403（`mcp_server.py:236-239`）；
2. `UserService.is_user_in_tenant()` → 403（`mcp_server.py:245-248`；`user/service.py:519-531`）；
3. `create_booking` 额外校验 `schedule.tenant_id != ctx.tenant_id` → 抛 `ToolBusinessError("排期不存在", 404)`（`mcp_server.py:580-581`）；
4. Service/Repository 再经 TenantAware 查询过滤（如 `membership/service.py:1153-1156` 的推荐卡路径也会显式比对租户）。

结论：**跨租户读写已实现多层拦截**。

### 5.3 发现的租户相关弱点

| 编号 | 描述 | 等级 | 依据 / 影响 |
|---|---|---|---|
| T-1 | `x-tenant-id` 分支直接信任数字头，**未校验租户存在与 ACTIVE 状态**；只有 `x-tenant-slug` 分支做了状态校验 | 低（对 AI 链路由 JWT 覆盖，无法据此越权） | `tenant_middleware.py:120-127` vs `130-145`。若未来有接口仅依赖 header 租户并跳过登录，则升级为中/高 |
| T-2 | 中间件租户与 JWT 租户**不一致时不报错**，只由后续 `get_current_user` 覆盖 | 低 | `tenant_middleware.py:95` → `auth.py:62`。当前 Tool 使用 JWT 值，无数据泄露；但“请求声称租户”和“实际租户”不一致被静默忽略，审计日志难以发现探测行为 |
| T-3 | `tenant_query.py` 在 ContextVar 为空时**跳过注入**（`40-45`），不是 fail-closed | 低（Tool 路径必有值） | 若有新代码在无租户上下文下调用 Repository，会退化为无过滤查询；属结构性风险，建议改为“无租户即报错” |

---

## 6. 参数注入与越权数据访问

### 6.1 身份参数注入

| 攻击尝试 | 结果 | 依据 |
|---|---|---|
| body 传 `user_id` / `tenant_id` | 被 Pydantic 模型忽略（模型无这些字段） | `modules/ai/router.py:30-32` |
| 让 LLM 在 Tool 参数中塞 `user_id` | `_filter_arguments` 丢弃；Tool 内 `_gate` 比对不一致 403 | `mcp_server.py:659-661,236-239` |
| 前端伪造 `x-tenant-slug` 查看别人的租户 | Tool 用 JWT 租户；SLUG 只影响入站路径 | `auth.py:62` |
| 传别人 `booking_id` 取消 | `BookingService.cancel_booking` 校验 `booking.student_id != student_id` → PermissionException；跨租户先被 Repository 过滤为 NotFound | `booking/service.py:264-271` |
| 传别人 `schedule_id` 预约 | Service 校验名额/时间/卡归属；Tool 先校验排期租户；扣次用本人卡 | `mcp_server.py:580-581`；`booking/service.py:72-180` |
| `get_my_bookings` 想看别人的 | Tool 固定 `self_only=True`，Service 强制 `student_id=user_id` | `mcp_server.py:498-507`；`booking/service.py:1203-1205` |
| `get_my_balance` 想看别人的 | Tool 无任何“目标用户”参数，Service 用 `ctx.user_id` | `mcp_server.py:537-545` |
| `query_*` 遍历全租户 | 设计即租户内公开查询，无跨租户能力 | `mcp_server.py:371-380,417-425` |

### 6.2 文本协议注入（Tool 输出 → Runtime 解析）

**问题**：`query_schedules` 把 DB 字段用 `|` 和换行拼接为文本协议（`mcp_server.py:432-448`），Runtime 在缺少结构化数据时才用正则解析（`runtime.py:729-755`）。

**已缓解（08031c4）**：
- `_safe_cell` 将 `|` 替换为全角 `｜`、换行折叠为空格并剔除非打印控制字符（`mcp_server.py:651-656`），`teacher_name/course_name` 均经转义（`442-444`）。
- Runtime 优先消费 `ToolOutcome.data`（`runtime.py:712-727`），只有 `data` 缺失时才回退文本解析。

残余：文本回退路径仍存在，若未来新增 Tool 输出未转义字段，可再次出现伪造选项；且用户仍可能被诱导预约同租户内另一个**真实**排期。
等级：**中低**（数据完整性/社工风险，非直接越权）。依据：`mcp_server.py:432-460,651-656`、`runtime.py:356-366,700-755`。

### 6.3 会话 ID 注入

- `session_id` 无长度/字符集校验（`modules/ai/router.py:32`），可包含任意字符并被拼进 Redis key（`session.py:39-57`）。
- 由于 key 固定带 `user_{user_id}` 前缀，**无法跨用户读取**；但可制造超长 key、浪费内存，或利用 `:` 等字符生成结构混淆的 key。
- 学员端每次进入生成新 `session_..._{entryTs}`（`ai-assistant/index.vue:46-47`），教师端默认 `session_{userId}`（`AiChatPanel.vue:192-198`）。
- 等级：**低**。依据：`router.py:32`、`session.py:39-57`。

---

## 7. 提示词注入（LLM 维度）

当前状态：**无 LLM → 提示词注入不可被模型执行**（见调用链文档 Q5）。
- System Prompt 已预置防护指令：防“忽略以上指令”、防复述系统提示、写操作需用户确认（`prompts.py:13-33`，关键条目 `24-25`）。
- `build_runtime_context` 显式声明“身份来源：登录态”“禁止跨用户/租户”“身份参数不得由用户消息指定”（`prompts.py:37-56`，身份行 `48-49`）。
- System Prompt 原文只写入日志指纹与长度（`runtime.py:77-84`），不回传前端；测试断言前端响应不含提示词（`tests/unit/test_ai_p0_stability.py:86-105`）。

风险（面向未来接入 LLM）：
| 编号 | 描述 | 等级（接入 LLM 后） | 依据 |
|---|---|---|---|
| P-1 | 规则引擎把用户原文拼进“无法识别您的输入「…」”等回复，若未来把历史再喂给 LLM，用户文本可携带注入指令 | 中 | `runtime.py:566-569,670-680`；`session.py:108-117`（`get_context` 已存在但当前无人调用） |
| P-2 | System Prompt 含 `user_id/tenant_id` 明文数字，若模型复述会泄露内部标识（非机密但属内部信息） | 低 | `prompts.py:48-49` |
| P-3 | 工具返回的 DB 文本（课程名/教师名）会进入 LLM 上下文，构成间接提示注入面 | 中 | `mcp_server.py:432-460`（`_safe_cell` 仅处理分隔符，不防语义注入） |

结论：**部分实现**（防护文案已就绪，但真实 LLM 调用面尚未存在，防护未被实战验证）。

---

## 8. 敏感数据、PII 与异常信息泄露

| 检查项 | 结论 | 依据 |
|---|---|---|
| 错误信息回显 SQL/堆栈/表名 | 已实现防护。`_INTERNAL_PATTERN` 命中（select/insert/update/delete/traceback/sqlalchemy/asyncpg/password/secret/token/`://`/file/line N）→ 统一兜底；超 200 字符也兜底 | `mcp_server.py:76-81,183-188,698-713` |
| 系统异常 | 只写日志 `tool + error_type`，用户侧统一“操作失败…” | `mcp_server.py:714-723` |
| Runtime 二次映射 | 关键词 → 友好提示，兜底不回显原文；测试覆盖 `SELECT/DROP` 不出现在响应 | `runtime.py:579-612`；`tests/test_mcp_tool_authorization.py:259-268` |
| Tool 返回字段最小化 | 无手机号/邮箱；仅课程名、时间、教师名、预约 ID、课时数 | `mcp_server.py:381-388,432-460,509-523,542-545,606-612,643` |
| 日志 PII | trace 只记 `input_length`，不记正文；但 `runtime.py:146-148` 会记录 `params`（keyword/date/booking_id），非 PII | `runtime.py:196-210` |
| 日志内部标识 | trace 明文记录 `user_id`、`tenant_id`（内部标识，非机密） | `runtime.py:196-210` |
| Redis 中 PII | 用户原文与 AI 回复以明文 JSON 存 Redis，TTL 3600s；若用户在对话里输入手机号会被留存 1 小时 | `session.py:72-98` |
| Token 泄露 | AI 不返回 Token；前端请求头注入由 `api/index.ts:241-245` 统一处理 | 已实现 |

等级评估：**低**（当前无 SQL/堆栈泄露；Redis 明文历史属常规缓存风险，建议后续做脱敏或缩短 TTL）。

---

## 9. 其他安全发现

| 编号 | 发现 | 等级 | 依据 |
|---|---|---|---|
| A-1 | `/api/v1/ai/chat` **无速率限制**。`RATE_LIMIT_CONFIG` 定义但从未注册；`RateLimiterMiddleware` 类存在但未 `add_middleware` | 中 | `apps/api/src/app/main.py:209-213`；`middleware/rate_limiter.py:235`；AI 路由无装饰器（`modules/ai/router.py` 全文） |
| A-2 | `GET /api/v1/ai/intents` 暴露规则引擎关键词、示例与内部描述（标注“调试用”），任何登录用户可读 | 低 | `modules/ai/router.py:110-119`；`intent.py:45-64,200-216` |
| A-3 | `DELETE /ai/history` 只清历史，遗留 `ai:state:*`，下一轮可能仍进入 pending 分支 | 低 | `modules/ai/router.py:102-107`；`session.py:100-106,149-155` |
| A-4 | `ChatResponse` 返回 `latency_ms`、`has_pending_state`，属内部运行信息，泄露面很小 | 低 | `modules/ai/router.py:71-81` |
| A-5 | 每个 Tool 自建 `SessionLocal`（非请求共享 session），事务边界在 Service；若 Service 未 commit 则不会落库，设计上可接受 | 低（架构一致性） | `mcp_server.py:364,406,490,532,567,629` |
| A-6 | `exclude_args` 在 FastMCP 3.4.7 已弃用（运行期告警），未来升级若行为变化可能使身份参数重新出现在 schema | 低 | 实测告警；`mcp_server.py:348` 等 |
| A-7 | 并发锁失败返回“正在处理上一个请求”，同一用户不同 `session_id` 可并行发起多次写操作（锁按 session 粒度，不按 user 粒度） | 低 | `runtime.py:61-64,618-637` |

---

## 10. 四个必答问题

### Q1 Tool 能否识别登录用户？
**能**。路径唯一：JWT → `get_current_user` → `current_user["user_id"]` → `AgentRuntime` → `ToolContext` → `_gate` → `ctx.user_id`。Tool 内所有归属判断都用该值（`get_my_bookings` 强制 `self_only`、`get_my_balance` 用 `ctx.user_id`、写操作 `student_id=ctx.user_id`）。依据：`deps/auth.py:40-66`、`modules/ai/router.py:47-56`、`runtime.py:232-244`、`mcp_server.py:224-233,498-507,537-545,601-605,637-642`。

### Q2 能否被篡改参数查别人数据？
**不能**（跨用户/跨租户）。三道防线：模型白名单过滤身份参数（`mcp_server.py:659-661`）、`_gate` 显式拒绝不一致身份（`236-239`）、Service 归属校验（`booking/service.py:268-269,1203-1205`）+ 租户三层隔离。残余：同租户内 `booking_id` 枚举可能通过错误文案探测“存在/不存在”（低）。

### Q3 是否可能绕过 RBAC？
**当前不能**。Tool 授权基于 DB 角色集合，且不使用 `PERMISSION_CHECK_BYPASS`；查库失败 fail-closed。唯一理论绕过是**进程内直接构造 `ToolContext` 调 `execute_tool`**，属代码级信任边界（当前仅 Runtime 使用，grep 已确认）。若未来开放给外部 Agent，必须把“身份注入”做成不可由调用方指定的受控通道（见 §11）。

### Q4 若暴露给外部 Agent 需要补什么？
1. **传输层认证**：MCP 不得以匿名 stdio 暴露给外部；使用受认证的 Streamable HTTP（mTLS / OAuth2 / 网关签名）+ 每请求短期凭证。
2. **身份代理**：外部 Agent 不能自报 user_id/tenant_id；必须由 Agent API（本系统）用 JWT 换取一次性的“Tool 调用票据”，服务端据此构造 `ToolContext`，并把票据绑定 `session_id + user + tenant + exp`。
3. **去掉 `execute_tool(context=...)` 的公共可传参**：改为内部私有方法 + 受控 broker；任何外部请求不得传入 context。
4. **Tool schema 收敛**：保留 `exclude_args`/改用 `Depends()` 的等价机制，确保 identity 永不出现在对外 schema。
5. **逐 Tool 速率与审计**：per-user/per-tenant 限流、写操作审计日志（tool、结果、耗时、票据 id），并纳入现有日志体系。
6. **写操作二次确认**：服务端强制“预演 → 确认 token → 执行”，禁止 Agent 连续自动执行多个写操作（`.trae/rules/ai/mcp.md` 要求）。
7. **输出结构化**：不再用文本协议返回（消除 §6.2 注入面），改 JSON Schema，并对字符串做转义/长度限制。
8. **网络面收敛**：若启用 HTTP transport，必须放在内网/网关后，绝不公网直连；stdio 只允许同机受控进程。
9. **租户白名单**：外部 Agent 只能访问其被授权租户；拒绝一切跨租户查询。
10. **JWT 传递**：禁止把用户 JWT 直接透传给 Agent/模型；使用短时票据。

---

## 11. 风险汇总（按等级）

**高**：无（当前未发现可直接越权/跨租户/命令执行的高危问题；前提是“Tool 无外部 RPC 入口”成立）。

**中**
- T-1/T-2 租户头与 JWT 不一致静默处理、`x-tenant-id` 不校验租户状态（对 AI 被 JWT 覆盖，但结构风险）。
- §6.2 `query_schedules` 文本协议（已转义且优先用结构化 `data`，风险降为中低；文本回退路径仍在）。
- A-1 `/ai/chat` 无限流。
- §4.3 进程内 `execute_tool(context=...)` 信任边界（当前不可利用，外部化后升级为高）。

**低**
- T-3 无租户 ContextVar 时 ORM 跳过注入。
- §6.3 `session_id` 无校验。
- §7 提示词注入（当前无 LLM）。
- A-2/A-3/A-4/A-5/A-6/A-7。
- Redis 明文会话历史 1 小时。

---

## 12. 未经验证

1. **未经验证**：生产 Redis 是否开启 ACL/加密传输与持久化策略（代码只读取 `REDIS_URL`，`deps/auth.py:23-26`）。
2. **未经验证**：网关/Nginx 是否对 `/api/v1/ai/*` 额外做了限流或 IP 白名单（仓库 compose 仅暴露 `127.0.0.1:8000`，`docker-compose.prod.yml:60-61`；仓库内无 Nginx 配置被本次审计覆盖）。
3. **未经验证**：线上是否存在绕过 API 直连数据库/Redis 的运维通道（超出代码审计范围）。
4. **未经验证**：`x-tenant-id` 分支在生产是否实际被任何客户端使用（小程序只用 `x-tenant-slug`，`api/index.ts:241-245`）。
5. **未经验证**：Tool 输出文本协议注入是否已在真实租户数据中出现（仅代码层推断，未查库）。
6. **未经验证**：`PERMISSION_CHECK_BYPASS` 在当前部署环境实际取值（默认 `False`，`core/config.py:57`；环境变量未在仓库内固定）。
