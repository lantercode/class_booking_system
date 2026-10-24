# Multi-Agent 协作流程规范 v3

> **Protocol Version**: v3
> **Previous Version**: v2（`docs/ai/workflows/multi-agent-collaboration-v2.md`）
> **日期**: 2026-09-23
> **Change Summary**:
> - Added frontend-engineer（第 5 个 Agent，覆盖 4 个前端 App + 共享包）
> - Updated responsibility matrix（新增前端职责行/列与跨端职责边界）
> - Updated collaboration workflow（Phase 0-8 插入前端轨道与 API Contract Freeze）
> - Updated handoff dependencies（Architect→Frontend、Frontend→Backend、Frontend→MCP、Frontend→Test[条件性]）
> - 新增 API Contract Freeze / AI UI Capability Gate / 多端差异声明 / 前端自验 4 条固化规则（R5-R8）
>
> **适用范围**: class_booking_system 全部跨端特性（任何触及 `apps/admin-web`、`apps/student-web`、`apps/teacher-web`、`apps/miniapp`、`packages/api-client`、`packages/api-types` 的任务）。纯后端任务仍可使用 v2 流程，v3 完全向后兼容。

---

## 0. 升级背景

v2 协作时 Team 只有 4 个 Agent（architect / backend / database / mcp），AI 课程查询特性全部落在 `apps/api/src/app/ai/` 目录内，无前端改动。

当前 Team 新增 **frontend-engineer**，且项目实际包含 **4 个前端端**：

| App | 技术栈 | API 层 | 状态管理 |
|-----|--------|--------|---------|
| `apps/admin-web` | Vue3 + Vite + Element Plus + TS | `@dance-saas/api-client`（axios，相对路径 `/api/v1`） | Pinia |
| `apps/student-web` | Vue3 + Vite + Element Plus + TS | `@dance-saas/api-client` | Pinia |
| `apps/teacher-web` | Vue3 + Vite + Element Plus + TS | `@dance-saas/api-client`（待核实，见 §11 UNKNOWN） | Pinia |
| `apps/miniapp` | uni-app + Vue3 + TS（mp-weixin），**npm 非 pnpm** | 独立 `src/api/index.ts`（`uni.request` + 绝对 URL `VITE_API_BASE_URL`） | Pinia |

共享包：

- `packages/api-client`：axios 封装，401 自动 refresh + retry，`x-tenant-slug` 头注入，统一解包 `{code,msg,data}`
- `packages/api-types`：由 FastAPI OpenAPI 生成（`pnpm gen:types`）
- AI 对话 UI 已存在：`apps/miniapp/src/components/AiAssistant.vue` → `aiChatApi` → `POST /api/v1/ai/chat`

v2 没有定义任何前端职责、前后端契约冻结点、多端差异处理、前端产物与前端评审，因此必须升级，而不是简单增补一段文字。

---

## 1. 十个维度的影响分析（升级决策依据）

| # | 维度 | v2 状态 | v3 决策 |
|---|------|--------|--------|
| 1 | Agent Team | 4 人 | 5 人：新增 frontend-engineer。**不新增** test-engineer（当前未配置，见 §11），其交接定义为条件性接口 |
| 2 | Responsibility Matrix | 仅后端向 | 增加前端行 + "契约消费/多端/UI 状态/AI 前端" 责任域；明确前端禁区（不直连 DB、不拼 MCP 参数、不发明端点） |
| 3 | Agent Selection | 默认全上 | 按"触端矩阵"选择：纯后端任务不召前端；触 AI 对话 UI 必须同时召 mcp + frontend |
| 4 | Architect → Frontend 交接 | 无 | 新增标准交接包：受影响 App 清单、API 契约、鉴权/租户头、页面/路由变更、流式能力判定（§6） |
| 5 | Frontend → Backend API Dependency | 隐式 | 显式化：OpenAPI 为唯一契约源，`pnpm gen:types` 同步，契约冻结点在 Phase 1/3，冻结后变更必须重新交接 |
| 6 | Frontend → MCP / AI Agent 依赖 | 无 | 前端**只**消费 `/api/v1/ai/chat`，永远不直连 MCP、不组装 tool 参数；Streaming / Tool Status UI 受 Capability Gate 约束（§7） |
| 7 | Frontend → Test Engineer 交接 | 无 | 当前 Team 无 test-engineer → 定义条件性交接接口（§8）；在该角色落地前，前端测试由 frontend-engineer 自验 + Architect 抽检 |
| 8 | Cross-Agent Review | 三方评审 | 四方评审，新增前端检查清单与"契约漂移"互评（§9） |
| 9 | Artifact 目录与命名 | 只有 backend/database/mcp | 新增 `implementation/<feature>-frontend.md`，架构文档强制含 "Frontend Impact" 节（§10） |
| 10 | Reconciliation | 三方汇总 | 四方汇总，新增 3 类冲突面：契约漂移、流式能力错配、双 API 层分叉（§11 冲突机制） |

---

## 2. Agent Team v3

```
                    ┌─────────────────────┐
                    │  project-architect  │  编排 / 调用链 / 契约冻结 / 冒烟设计
                    └──────────┬──────────┘
          ┌──────────┬────────┼────────┬──────────────┐
          ▼          ▼        ▼        ▼              ▼
  frontend-   backend-  database-  mcp-      (test-engineer:
  engineer    engineer   engineer   engineer   当前未配置，条件性预留)
```

### 编排原则（沿用 v2，不变）

- Architect 是唯一编排者，Specialist 之间不互相派活
- Specialist 只对 Architect 的交接包负责，不代替其他角色做结论
- 所有跨角色矛盾回到 Phase 3 Reconciliation 仲裁，不在实施阶段私下妥协

---

## 3. Frontend Engineer（新增角色）

### 3.1 职责范围

| 责任域 | 具体内容 | 代码落点 |
|--------|---------|---------|
| Vue 3 | Composition API、SFC、响应式状态、生命周期 | 4 个 App 的 `src/` |
| TypeScript | 严格类型、与 `packages/api-types` 对齐，禁止 `any` 掩盖契约漂移 | 全部 `.ts/.vue` |
| uni-app / 微信小程序 | mp-weixin 编译、`pages.json`/`manifest.json`、WeChat DevTools 验证、`npm`（非 pnpm）约束 | `apps/miniapp` |
| API Integration | web 三端用 `@dance-saas/api-client`；小程序用 `src/api/index.ts`；两端均遵守 `{code,msg,data}` 信封 | `packages/api-client/src/*.ts`、`apps/miniapp/src/api/` |
| Pinia | Store 设计、auth/tenant 状态、与 localStorage（token / tenantSlug）同步 | 各 App `stores/` |
| Components | 复用/扩展组件；admin 端 Element Plus；小程序端自研 `App*` 组件体系，不引入跨端 UI 库 | `components/` |
| UI/UX | loading / empty / error / 无权限 四态必做；多端交互差异（tap vs click、scroll-view） | 页面与组件 |
| AI Chat UI | `AiAssistant.vue` 演进：消息流、快捷动作、历史、未读、多轮 pending 状态展示 | miniapp 组件 |
| Streaming UI | **前瞻性职责**：SSE/流式渲染、打字机、中止（abort）。当前后端非流式，受 §7 Gate 约束，禁止提前写假流式 | miniapp / 未来 web |
| Tool Calling Status UI | **前瞻性职责**：展示"正在查询课表/正在预约"等工具执行态。依赖后端在 chat 响应中返回 tool trace，当前契约不存在 | miniapp |
| Frontend Testing | `vue-tsc` 类型检查、生产构建、小程序真机/DevTools 验证；`uni-automator`（已有依赖）自动化为预留方向 | 各 App |

### 3.2 前端禁区（不可越界）

```
❌ 直连 PostgreSQL / Redis（不写 SQL、不连数据库）
❌ 绕过 /api/v1/ai/chat 直接对接 MCP Server
❌ 在前端组装/注入 user_id、tenant_id 作为业务参数（身份只走 Header/Token，由后端 Runtime 注入）
❌ 发明后端不存在的端点（如 v1 审计中 membership.ts 的 delete()/batchDelete() 即此类事故）
❌ 在 web 端硬编码绝对 API URL；在小程序端复用浏览器 axios/localStorage
❌ 手改 packages/api-types 生成产物
❌ 把 System Prompt、工具密钥、内部错误堆栈暴露到 UI
```

### 3.3 前端专属检查（不可委托，对应 v2 R1）

```
✅ 受影响 App 矩阵：admin / student / teacher / miniapp 哪些要改，逐一列明
✅ 契约一致性：调用的每个端点在 OpenAPI 中存在，方法/参数/响应字段逐一核对
✅ 类型来源：请求/响应类型来自 packages/api-types 或 api-client 导出，不本地重复定义
✅ 鉴权链路：Authorization 头、x-tenant-slug 头、401 refresh 行为是否成立（小程序走独立层时同样成立）
✅ 四态完整：loading / empty / error(含 403/409/500) / 成功
✅ 多端差异：web 与 mp-weixin 的 API 层、存储、导航、样式差异已分别处理
✅ AI UI 安全：不回显内部 traceback；用户输入长度与后端一致（message ≤ 500）；不提供绕过确认的直接写操作入口
✅ 构建自验：vue-tsc + 目标端构建通过后方可送审（R8）
```

---

## 4. Agent Responsibility Matrix v3

> 图例：R = Responsible（执行），V = Verify（验证他人结论），C = Consulted（咨询），— = 不参与

| 责任域 | Architect | Frontend | Backend | Database | MCP |
|--------|:---------:|:--------:|:-------:|:--------:|:---:|
| 全局调用链（UI → API → Router → Service → Repo → DB） | R | V(前端段) | V(后端段) | V(数据段) | V(AI段) |
| 受影响 App / 文件清单 | R | V+C | V+C | — | V+C |
| API 契约（路径/方法/参数/响应/错误码） | R(冻结) | V(消费) | R(实现+OpenAPI) | — | C(AI 端点) |
| TS 类型生成与消费 | C | R | C（保证 OpenAPI 准确） | — | — |
| Pydantic 校验 / 业务规则 | — | — | R | — | — |
| Service 事务边界 / 行锁 / 幂等 | C | — | R | V | — |
| 索引 / 约束 / Migration / 锁表风险 | C | — | C | R | — |
| 租户隔离 / RBAC / 鉴权链路 | R(全局) | V(Header 段) | R(服务端) | V | R(AI Tool 段) |
| MCP Tool 契约 / 鉴权 / Prompt 注入 | C | — | — | — | R |
| AI Chat 响应契约（含未来 SSE / tool trace） | R(冻结) | V(消费) | R(chat 接口) | — | R(Runtime/Tool 段) |
| Pinia / 组件 / 页面 / 多端 UI | — | R | — | — | — |
| Streaming UI / Tool Status UI | C(Gate 判定) | R(契约就绪后) | R(SSE 产出) | — | R(trace 产出) |
| 前端测试与构建自验 | V | R | — | — | — |
| pytest / 集成测试 | V | — | R | C | C |
| 冲突仲裁 / Reconciliation | R | C | C | C | C |
| 最终报告汇总 | R | C | C | C | C |

---

## 5. Agent Dependency Graph v3

```
                         project-architect
                              │
            ┌─────────────────┼──────────────────────┐
            │                 │                      │
   ┌────────▼───────┐  ┌──────▼──────┐        ┌──────▼──────┐
   │ backend-       │  │ database-   │        │ mcp-        │
   │ engineer       │  │ engineer    │        │ engineer    │
   │                │  │             │        │             │
   │ OpenAPI 产出 ──┼──┼─ Migration  │        │ Tool/Runtime│
   └───────┬────────┘  └─────────────┘        └──────┬──────┘
           │                    ▲                    │
           │ ① OpenAPI 契约冻结  │                    │ ② /ai/chat 响应契约
           │ (唯一事实源)        │                    │   (含未来 SSE/trace)
           ▼                    │                    ▼
   packages/api-types ──gen:types──▶ packages/api-client
                                          │
                              ③ 契约消费   │
                          ┌───────────────┴───────────────┐
                          ▼                               ▼
                 web 三端 (axios 层)              miniapp (uni.request 层)
                 frontend-engineer                frontend-engineer
                          │                               │
                          └────────── ④ 条件性 ───────────┘
                                      ▼
                          test-engineer（当前未配置；
                          未配置前由 frontend 自验 + Architect 抽检）
```

依赖方向铁律：

1. **单向依赖**：Frontend → Backend 契约；Backend 永远不反向依赖前端实现
2. **契约先行**：后端先发布 OpenAPI / chat 响应契约，前端再编码
3. **前端不触达** Database 与 MCP Runtime；两者的变化只能通过 API 契约传导到前端
4. MCP Tool 的增改若不改变 `/ai/chat` 的输入输出，前端**无需改动**，Architect 不得空召前端

---

## 6. Handoff 协议 v3

### 6.1 Architect → Frontend（新增，标准交接包）

Architect 在 Phase 1 结束前必须向前端交付：

```markdown
## Frontend Handoff Package
1. 受影响 App 矩阵：[ ] admin-web [ ] student-web [ ] teacher-web [ ] miniapp
2. 页面/路由/组件变更清单（含新建 vs 修改）
3. API 契约表：
   | 方法 | 路径 | 请求体关键字段 | data 响应结构 | 可能错误码 |
   |------|------|--------------|--------------|-----------|
4. 契约来源：OpenAPI commit / 已冻结的接口文档（不允许口头约定）
5. 鉴权要求：是否登录、是否需要 x-tenant-slug、是否有 RBAC 按钮级权限
6. AI UI 专项（如涉及）：
   - 当前 /ai/chat 是否流式：否（现状）/ 是（需给出 SSE 事件契约）
   - 响应是否含 tool trace：否（现状）/ 是（需给出字段定义）
7. Pinia / 缓存影响：是否需要新 Store 或改 auth/tenant 状态
8. 多端差异点：web 与 mp-weixin 是否行为一致
9. 前端冒烟用例（R3 延伸）：最小可验证操作路径
```

交接包缺项时，frontend-engineer 有权拒绝开工并退回 Architect（对应 v2 "禁止用猜测填补不确定性"）。

### 6.2 Frontend → Backend（API Dependency）

- 前端只消费**已冻结**契约；契约未就绪时，可在 Architect 批准下按契约草稿配 mock（各 App 已有 `mock/` 目录），但必须登记 mock 清单并在联调阶段删除
- 联调中发现契约与实现不符 → 不在前端"兼容脏数据"，回 Reconciliation 修后端或修契约
- 后端改契约（字段增删、错误码变化）→ 必须重新生成 OpenAPI 并由 Architect 触发**二次交接**，前端执行 `pnpm gen:types` 后评估影响
- 已知坑位（交接提醒，源自 CLAUDE.md）：
  - 后端 `redirect_slashes=False`：集合端点不要加尾斜杠
  - 统一信封 `{code,msg,data}`：业务错误在 HTTP 状态码 + body，前端不得只看 HTTP 200
  - 401 自动 refresh/retry 已在 api-client 实现；小程序层在 `src/api/index.ts` 独立实现，改动需两端同步
  - v1 审计教训：前端 API 对象出现过后端不存在的 `DELETE /membership/cards/{id}` 与 `batch-delete` —— 契约核对必须逐方法进行，不能凭命名想当然

### 6.3 Frontend → MCP / AI Agent

- 前端唯一接触面：`POST /api/v1/chat`、`GET/DELETE /api/v1/ai/history`、`GET /api/v1/ai/intents`（已核实，见 `modules/ai/router.py`）
- 前端**禁止**：直连 FastMCP stdio、在请求体传 user_id/tenant_id、本地实现意图识别/工具路由
- MCP/Tool 层的变更只有在引起 chat 接口契约变化时才传导给前端；不引起契约变化的 Tool 重构（如 v1.1 把 Tool 改为复用 Service）对前端透明
- 写操作类 Tool（create_booking / cancel_booking）的 UI 必须保留**用户确认步骤**，前端不提供"一句话直接下单无确认"入口（纵深防御，与 MCP 安全审查结论一致）

### 6.4 Frontend → Test Engineer（条件性交接）

当前 Team **未配置** test-engineer。v3 预先定义交接接口，待该角色配置后立即生效：

```
交接输入：受影响 App 矩阵、冒烟用例、构建产物路径、小程序体验版/DevTools 工程路径
验收输出：端到端用例结果、多端差异缺陷、契约一致性缺陷
触发条件：跨 2 端以上的特性 / 涉及支付与约课写操作 / AI 对话链路改动
```

在该角色落地前：
- 前端单元/组件/构建验证由 frontend-engineer 自验（R8）
- 端到端与多端回归由 Architect 在 Phase 6 组织人工冒烟
- 不允许因为"没有测试 Agent"而跳过前端验证环节

---

## 7. AI UI Capability Gate（新增卡点）

**已核实事实**（`apps/api/src/app/modules/ai/router.py`，2026-09-23）：

- `POST /api/v1/ai/chat` 为**一次性 JSON 响应**：`data = {response, session_id, timestamp, has_pending_state, latency_ms}`
- **无 SSE / chunked 流式**；**无 tool_calls / 工具执行过程 trace 字段**

因此：

| 前端能力 | 后端契约现状 | Gate 结论 |
|---------|-------------|----------|
| AI Chat UI（消息、历史、loading dots） | 就绪 | 可实施 |
| Streaming UI（流式打字机、中止） | **未就绪** | 禁止先行实施；如特性需要，先由 backend+mcp 产出 SSE 事件契约并冻结，再排前端 |
| Tool Calling Status UI（"正在查询/预约中"状态） | **未就绪**（无 trace 字段） | 同上；需后端在响应或 SSE 事件中定义 tool 状态结构 |
| 意图调试展示 | 就绪（`GET /ai/intents`） | 管理/调试用途可实施 |

Gate 判定在 Phase 1 由 Architect 做出并写入交接包；前端若在实施中发现需要 Gate 外能力，停工回 Reconciliation，不得用 setInterval 假流式、本地伪造工具状态等方式绕过。

---

## 8. Feature Workflow v3（Phase 0-8）

```
Phase 0: Project Reconnaissance
  ├─ 后端 4 探针（v2 不变）：代码结构 / DB / Redis / 鉴权租户
  └─ 前端探针（新增）：
      ├─ 触端矩阵（4 App 哪些相关）
      ├─ API 层现状（api-client vs miniapp/src/api）
      ├─ 类型现状（api-types 是否含目标资源）
      └─ mock/ 现状与 AI 组件现状

Phase 1: Architect Analysis
  ├─ Step 1: 问题识别（v2 不变）
  ├─ Step 2: 架构决策（v2 不变）
  └─ Step 3: 冒烟测试（v2 R3，扩展）
      ├─ 意图识别冒烟（如涉及，v2 模板）
      ├─ API 签名冒烟（如涉及）
      ├─ DB 查询能力冒烟（如涉及）
      ├─ 契约存在性冒烟（新增）：前端计划调用的每个端点在 OpenAPI/路由中真实存在
      └─ AI UI Capability Gate 判定（新增，§7）
  产出：Frontend Handoff Package（§6.1）+ 契约冻结（R5）

Phase 2: Specialist Analysis（并行四轨道）
  ├─ Backend（v2 专属清单不变）：[VERIFY] + 签名/透传/异常 + [NEW]
  ├─ Database（v2 R4 不变）：索引/锁/性能/约束 + 至少 1 个 [NEW]
  ├─ MCP（v2 专属清单不变）：契约/鉴权/校验/PII/Prompt 注入
  └─ Frontend（新增，§3.3 专属清单）：
      [VERIFY:handoff] 逐端点核对契约、逐 App 核对影响面
      类型缺口分析（gen:types 后是否仍需本地类型）
      四态与多端差异分析
      AI UI：对照 Gate 结论确认可实施范围
      [NEW] 独立发现（至少 1 个：交互/性能/类型/多端问题）

Phase 3: Architecture Reconciliation（四方）
  ├─ 汇总四方分析（v2 为三方，Changed）
  ├─ 仲裁 §11 的三类新冲突
  ├─ 契约变更 → 重新冻结并向前端二次交接
  └─ 确认 mock 清单（如允许并行开发）

Phase 4: Implementation Planning
  └─ 实施顺序（含前端后插入）：
     DB/Migration → Backend（含 OpenAPI 更新）→ gen:types
       → Frontend（按 App 矩阵）→ 联调删 mock
     可并行：MCP Tool 重构（不改 chat 契约时）与前端并行

Phase 5: Implementation
  ├─ 后端先行发布契约；前端在冻结点之后编码
  ├─ 前端按 App 分别提交，多端差异不跨端复制粘贴了事
  └─ 冒烟用例预期已在 Phase 1 通过，实施阶段不应出现"端点不存在"级意外

Phase 6: Testing
  ├─ 后端：ruff / mypy / pytest（v2 不变）
  ├─ 前端（新增，R8）：
  │   ├─ web：vue-tsc + 生产构建
  │   ├─ miniapp：vue-tsc + build:mp-weixin + WeChat DevTools 冒烟
  │   └─ 契约一致性：gen:types 后无类型报错、无残留 mock
  ├─ 联调：401 refresh、租户头、业务错误码四态
  └─ 冒烟回归（v2 不变）+ 前端交接包冒烟用例回归

Phase 7: Cross-Agent Review（四方，§9 清单）

Phase 8: Final Report（含 Frontend Impact 实测结论）
```

---

## 9. Cross-Agent Review v3

沿用 v2 R1/R2（专属检查不可委托、引用标记强制），新增：

### 9.1 Frontend Review Checklist

```
✅ 调用端点全部存在且与 OpenAPI 一致（逐方法核对，吸取 membership.ts 教训）
✅ 无本地重复定义的后端 DTO 类型；无手改 api-types
✅ web 无硬编码绝对 URL；小程序未误用 localStorage/axios
✅ Authorization / x-tenant-slug 在所选 API 层实际生效
✅ loading/empty/error(403/409/500)/成功 四态齐全
✅ 写操作（预约/取消/会员卡）有二次确认与失败回滚提示
✅ AI UI：无内部异常回显；输入长度与后端一致；Gate 外能力未偷渡
✅ vue-tsc + 目标端构建通过（R8 证据写入报告）
✅ 多端：同一特性在矩阵内每个 App 均有验证结论（含"不适用"理由）
```

### 9.2 互评新增项

- **Backend → Frontend**：核对前端是否正确处理新错误码/新字段，无"静默吞字段"
- **Frontend → Backend**：核对 OpenAPI 与实际行为一致（尤其可选字段是否真的可能为 null）
- **MCP → Frontend**：AI 对话 UI 的写操作确认、敏感信息展示是否符合 MCP 安全边界
- **Database/Backend 互评**：v2 已定义，不变

---

## 10. Artifact 目录与命名 v3

沿用现有目录结构，新增前端产物：

```
docs/ai/
├─ architecture/<feature>-architecture.md        # 必须含 "Frontend Impact" 节
│                <feature>-final.md               # 含冻结后的契约与触端矩阵
├─ implementation/
│   ├─ <feature>-backend.md                       # v2
│   ├─ <feature>-database.md                      # v2
│   ├─ <feature>-mcp.md                           # v2
│   └─ <feature>-frontend.md                      # 【v3 新增】
├─ tests/<feature>-test-report.md                 # 含前端构建/多端验证证据
└─ workflows/multi-agent-collaboration-v3.md      # 本文件
```

`<feature>-frontend.md` 必备小节：触端矩阵 / 契约引用（用 `[REF:arch]`）/ 类型与 api-client 变更 / Store 与组件 / 四态处理 / 多端差异 / Gate 结论 / 自验证据 / `[NEW]` 独立发现。

历史产物（v2 时代的 backend/database/mcp 三件套）保持有效，不补造 frontend 文档。

---

## 11. Conflict / Reconciliation v3

v2 的冲突机制（Architect 仲裁、引用标记、矛盾不进实施期）全部保留。新增三类高频冲突面与仲裁规则：

| 冲突面 | 典型表现 | 仲裁规则 |
|--------|---------|---------|
| API 契约漂移 | 前端调用字段后端没有；后端改字段未通知；前端"兼容"脏数据 | OpenAPI + `gen:types` 为唯一事实源（R5）；漂移一律改后端或正式改契约并重冻结，禁止前端兜底脏数据 |
| 流式/工具状态能力错配 | 前端要做打字机/工具进度，后端只有一次性 JSON | Capability Gate（§7）一票否决：契约未产出则前端不做；需要则现场补后端任务卡 |
| 双 API 层分叉 | web（axios api-client）与小程序（uni.request）鉴权/错误处理行为不一致 | 允许两套实现存在（运行时约束），但信封、401 refresh、租户头、超时/abort 语义必须一致；任一侧改动在交接包中列出双侧任务 |
| mock 残留 | 联调后 mock 未删，生产指向假数据 | Phase 6 强制检查 mock 清单归零（调试用途的 mock 文件需显式标注且不被生产入口引用） |
| 召之即来的空转 | 纯后端 Tool 重构也召前端 | Agent Selection（§1 维度3）：不改 chat 契约不召前端；Architect 对无效召集负责 |

Reconciliation 输出必须更新到 `<feature>-final.md`，并标注每次契约重冻结的版本号（如 contract v1 → v2），前端只认最新冻结版。

---

## 12. v2 保留内容（仍然有效，不变）

以下规则在 v3 中**原样保留**，继续适用于全部特性：

- **R1**：Agent 专属检查不可委托、不可跳过
- **R2**：引用标记强制使用（`[REF]` / `[VERIFY]` / `[NEW]`），前端产物同样适用
- **R3**：Phase 1 冒烟测试强制（v3 仅扩展两类前端相关冒烟，不削弱）
- **R4**：Database Agent 即使 No Change 也必须完成索引/锁/性能/约束四项独立检查并给至少 1 个 `[NEW]`
- 三层引用标记语义、写作模板
- Architect 专属：全局调用链、跨模块依赖、改动清单、冲突预判、冒烟设计
- Backend / Database / MCP 三方专属检查清单原文
- Analyze → Plan → Implement → Test → Review 总流程与 project_rules.md 全部既有条款

对纯后端/纯数据库任务，可直接走 v2 轨道（Phase 2 不召 Frontend），无需引用本文件的前端章节。

---

## 13. Deprecated / Changed（不删除，留痕）

| 项 | v2 | v3 处理 | 原因 |
|----|----|---------|------|
| Phase 2 Specialist 数量 | 三方（Backend/Database/MCP） | **Changed**：四方，新增 Frontend 轨道 | Team 扩编 |
| Reconciliation 参与方 | "汇总三方分析" | **Changed**：四方汇总 + 三类新冲突仲裁 | 同上 |
| 全局调用链检查 | Architect 清单中 "Frontend → API → …" 为抽象一行 | **Changed**：拆出前端探针、触端矩阵、双 API 层核实 | 前端已成独立责任域 |
| Artifact 集合 | architecture + backend/database/mcp + test report | **Changed**：新增 `-frontend.md`，架构文档强制 Frontend Impact 节 | 前端变更需留证 |
| Cross-Agent Review | 三方清单 | **Changed**：新增前端清单与互评项 | — |
| v2 优化效果评分 38/38 | 作为目标度量 | **Deprecated（作为 v3 目标）**：该评分只覆盖后端向协作维度，不含前端/多端；v3 不沿用该分母评分，改用 §9 清单通过制 | 避免指标失真 |
| 前端无角色、无交接、无产物 | v2 事实状态 | **Deprecated**：由 §3/§6/§10 取代 | — |

---

## 14. v3 新增固化规则（建议追加到 project_rules.md「Multi-Agent Collaboration」）

> 本节为协议规则文本；是否落入 project_rules.md 由用户决定，本次任务不修改该文件。

- **R5: API Contract Freeze** —— FastAPI OpenAPI 是前后端唯一契约源。Phase 1/3 冻结契约，后端保证 OpenAPI 与实现一致；前端通过 `pnpm gen:types` 消费，禁止调用未登记端点、禁止手改生成类型。契约任何增删改必须重冻结并二次交接。
- **R6: AI UI Capability Gate** —— Streaming UI 与 Tool Calling Status UI 必须等后端产出并冻结 SSE/工具状态契约后才允许实施；当前 `/ai/chat` 为非流式 JSON 且无 tool trace，禁止前端以假流式/伪造状态绕过。
- **R7: 多端差异声明** —— 每个特性必须在交接包声明受影响 App（admin/student/teacher/miniapp）；web axios 层与小程序 uni.request 层的信封、401 refresh、租户头、超时语义必须双侧一致。
- **R8: 前端送审前强制自验** —— web 端 `vue-tsc` + 生产构建、小程序 `vue-tsc` + `build:mp-weixin` + DevTools 冒烟全部通过，证据写入 test report，方可进入 Cross-Agent Review。

---

## 15. UNKNOWN / NEED_VERIFY

| # | 项 | 已检查 | 为何仍未知 | 下一步验证方式 |
|---|----|--------|-----------|---------------|
| U1 | 各 Agent 的实际系统提示/配置 | 检查 `.trae/`（不存在）、`AGENTS.md`、`.cursorrules`（均无） | Agent 配置在 TRAE 客户端侧，不在仓库 | 用户在 TRAE 配置界面核对 5 个 Agent 描述与 §3/§4 对齐 |
| U2 | test-engineer 角色 | 用户提供的已配置 Agent 仅 5 个，无 test-engineer | §6.4 只能定义条件性接口 | 用户确认是否计划配置；配置后激活交接并升级为 v3.1 |
| U3 | 前端测试框架选型 | web 两端 package.json 无 vitest/jest；miniapp 有 `@dcloudio/uni-automator` 依赖但无 test 脚本 | Frontend Testing 无既有事实标准 | 首次前端测试任务前由 Architect + Frontend 决策选型并补 R8 细则 |
| U4 | teacher-web API 集成方式 | 已确认 student-web/admin-web 依赖 `@dance-saas/api-client`；teacher-web 未逐字核实 | grep 只覆盖两端 | Phase 0 前端探针补查 teacher-web/package.json 与调用方式 |
| U5 | 各 App mock 与真实接口的混用程度 | student-web/admin-web 存在 `mock/` 目录 | 不确定哪些页面仍走 mock | 特性级 Phase 0 探针逐页面确认；联调阶段按 §11 mock 归零检查 |
| U6 | 未来 SSE / tool trace 契约形态 | 已核实 router.py 现状为非流式、无 trace | 契约尚未设计 | 后端启动流式改造时先出事件 schema，经 Reconciliation 冻结后解除 R6 Gate |

---

## 16. 结论

v3 不是 v2 的重写，而是把"前端"从 v2 调用链上的一个抽象名词升级为一等协作角色：契约冻结（R5）、能力门禁（R6）、多端声明（R7）、前端自验（R8）四条新规则与 v2 的 R1-R4 正交叠加。对纯后端任务 v2 轨道继续有效；凡触及四个前端 App、共享包或 AI 对话 UI 的任务，一律走 v3。
