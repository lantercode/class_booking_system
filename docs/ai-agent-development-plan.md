# 舞蹈机构 SaaS AI Agent 开发计划

> 基于 MCP Server + 自然语言查询 + AI Agent，将现有约课系统升级为智能业务系统

---

## 一、整体 AI Agent 架构设计

### 1.1 系统架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                         用户入口层                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │ 微信小程序     │  │ Vue Web 管理  │  │ Claude Desktop（开发）│    │
│  │ AI 对话组件   │  │ AI 助手面板   │  │                      │    │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘    │
└─────────┼─────────────────┼─────────────────────┼────────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Agent Runtime（代理运行时）                     │
│                                                                   │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐                 │
│  │ 会话管理  │  │ Intent 识别  │  │ 上下文记忆  │                 │
│  │ (Redis)  │  │ (LLM)        │  │ (多轮对话)  │                 │
│  └──────────┘  └──────────────┘  └─────────────┘                 │
│                                                                   │
│  ┌──────────────────────────────────────────────────┐            │
│  │              LLM Decision Engine                  │            │
│  │  ┌────────────────┐  ┌──────────────────────┐   │            │
│  │  │ Function Calling│  │ ReAct 推理链         │   │            │
│  │  │ 意图→参数提取   │  │ 思考→行动→观察→循环   │   │            │
│  │  └────────────────┘  └──────────────────────┘   │            │
│  └──────────────────────────────────────────────────┘            │
│                                                                   │
│  ┌──────────────────────────────────────────────────┐            │
│  │              MCP Client                           │            │
│  │  - 发现可用 Tools (list_tools)                    │            │
│  │  - 调用 Tools (call_tool)                         │            │
│  │  - 管理多 Server 连接                             │            │
│  └──────────────────────┬───────────────────────────┘            │
└─────────────────────────┼────────────────────────────────────────┘
                          │ MCP 协议 (stdio / SSE / HTTP)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MCP Server（工具注册层）                         │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐        │
│  │                    Tool Registry                       │        │
│  │  🔍 查询类          ✏️ 操作类         📊 分析类        │        │
│  │  ├─ query_courses   ├─ create_booking ├─ stats_weekly │        │
│  │  ├─ query_schedules ├─ cancel_booking ├─ stats_popular│        │
│  │  ├─ get_my_bookings ├─ check_in       └─ stats_teacher│        │
│  │  ├─ get_my_balance  └─ request_leave                  │        │
│  │  └─ get_teacher_today                                  │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐        │
│  │              Auth Middleware（鉴权中间件）              │        │
│  │  - JWT Token 透传 / - RBAC 角色校验                   │        │
│  │  - 租户隔离（tenant_id 自动注入）                      │        │
│  └──────────────────────────────────────────────────────┘        │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│              舞蹈 SaaS Backend API（现有系统，不改动）             │
│  Auth / Course / Schedule / Booking / Teacher / Classroom / Tenant│
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                       数据存储层                                   │
│  PostgreSQL（业务数据） + Redis（会话/缓存） + Milvus（可选 RAG）  │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 MCP Server 在系统中的职责

| 职责 | 说明 |
|------|------|
| **工具注册中心** | 将系统所有可用能力以 Tool 形式注册，告知 AI "这个系统能做什么" |
| **协议适配层** | 将 LLM 的工具调用请求翻译为后端 Service 调用，将 Service 返回翻译为 LLM 可读文本 |
| **安全网关** | 所有 Tool 调用都经过鉴权中间件，确保学生无法调用教师/管理员 Tool |
| **Schema 定义者** | 为每个 Tool 定义精确的输入参数 Schema，让 LLM 知道如何传参 |

### 1.3 Agent 如何发现和调用 MCP Tools

```
Step 1: 连接建立 → MCP Client → Server: initialize
Step 2: 工具发现 → MCP Client → Server: list_tools() → 返回所有 Tool 的 name + description + inputSchema
Step 3: LLM 决策 → System Prompt + Tool 列表 + 用户输入 → 决定调用哪个 Tool、传什么参数
Step 4: 工具调用 → MCP Client → Server: call_tool(name, arguments) → 后端 Service → 数据库
Step 5: 结果返回 → MCP Server → Client → LLM → 生成自然语言回复 → 用户看到结果
```

### 1.4 Tool 与传统 REST API 的区别

| 维度 | REST API | MCP Tool |
|------|----------|----------|
| 消费者 | 人类开发者（读文档、拼 URL） | AI Agent（自动发现、自动调用） |
| 描述方式 | OpenAPI JSON / Swagger 文档 | Tool name + description + JSON Schema |
| 调用方式 | 手动构造 HTTP 请求 | LLM 自动生成 function call |
| 错误处理 | HTTP 状态码（400/401/500） | 自然语言错误描述 + 业务码 |
| 组合能力 | 前端手动组合多个 API 调用 | Agent 自动编排多 Tool 调用链 |
| 状态管理 | 无状态 | 会话上下文（多轮对话记忆） |

### 1.5 为什么采用 MCP 而不是直接调用接口

**1. 工具发现 vs 文档阅读**

传统方式：AI 需要读懂 OpenAPI 文档 → 理解每个接口的用途 → 手动构造调用。MCP 方式：AI 调用 `list_tools()` → 自动获得所有可用工具及参数 Schema → 直接调用。

**2. 标准化协议 vs 定制集成**

MCP 是 Anthropic 推出的开放协议，已被 OpenAI、Google 等主流 AI 平台支持。系统可以对接任何 MCP 兼容的 AI 客户端（Claude Desktop、Cursor、Continue.dev），不需要为每个平台单独开发集成。

**3. 关注点分离**

MCP Server 层只关心定义工具和调用 Service，Agent Runtime 层只关心理解意图和编排 Tool 调用，后端 Service 层完全不感知 AI 的存在。

---

## 二、MCP Server 设计方案

### 2.1 Tool 全景图

```
MCP Server: dance-saas-agent
│
├── 🔍 查询类（只读，低风险）
│   ├── query_courses          搜索课程
│   ├── get_course_detail      课程详情
│   ├── query_schedules        查询排期
│   ├── get_my_bookings        我的预约
│   ├── get_booking_detail     预约详情
│   ├── get_my_balance         我的课时余额
│   ├── get_consumption_history 消费记录
│   └── get_teacher_today      教师今日课程
│
├── ✏️ 操作类（写入，中风险）
│   ├── create_booking         创建预约
│   ├── cancel_booking         取消预约
│   ├── request_leave          请假申请
│   └── check_in               签到
│
├── 📊 分析类（聚合，管理权限）
│   ├── analyze_weekly_stats   本周统计
│   ├── analyze_popular_courses 热门课程
│   └── analyze_teacher_workload 教师工作量
│
└── 💬 知识类（RAG，可选）
    ├── search_faq             搜索 FAQ
    └── get_refund_policy      退费政策
```

### 2.2 核心 Tool 详细设计

#### query_courses — 搜索课程

```yaml
name: query_courses
description: 搜索课程列表，支持按关键词、分类、难度等级筛选
inputSchema:
  type: object
  properties:
    keyword: { type: string, description: 搜索关键词，如"瑜伽"、"街舞" }
    category: { type: string, enum: [yoga, dance, fitness, kids, other] }
    level: { type: string, enum: [beginner, intermediate, advanced] }
    page: { type: integer, default: 1 }
    page_size: { type: integer, default: 5 }
权限: student, teacher, admin
```

#### query_schedules — 查询排期

```yaml
name: query_schedules
description: 查询指定日期范围内的排期列表，支持按课程、教师、教室筛选
inputSchema:
  properties:
    keyword: { type: string, description: 课程名称关键词 }
    date: { type: string, description: 日期，格式 YYYY-MM-DD }
    start_date: { type: string, description: 开始日期 }
    end_date: { type: string, description: 结束日期 }
    teacher_name: { type: string, description: 教师姓名 }
    page: { type: integer, default: 1 }
权限: student, teacher, admin
```

#### get_my_bookings — 我的预约

```yaml
name: get_my_bookings
description: 查询当前用户的预约记录，支持按状态筛选
inputSchema:
  properties:
    status: { type: string, enum: [pending, confirmed, completed, cancelled, checked_in] }
    page: { type: integer, default: 1 }
权限: student（仅自己）、teacher（仅自己学生）
实现要点: 自动注入当前用户 user_id，不允许通过参数指定其他用户 ID
```

#### get_my_balance — 我的课时余额

```yaml
name: get_my_balance
description: 查询当前用户的课时余额（总购买、已消耗、剩余）
权限: student（仅自己）
```

#### get_teacher_today — 教师今日课程

```yaml
name: get_teacher_today
description: 查询教师当天的排课列表
权限: teacher（仅自己）、admin
```

#### create_booking — 创建预约

```yaml
name: create_booking
description: 为当前用户预约指定排期的课程，自动校验名额、时间冲突
inputSchema:
  properties:
    schedule_id: { type: integer, description: 排期ID }
  required: [schedule_id]
权限: student
安全:
  - 不允许为他人预约（user_id 自动注入当前用户）
  - 校验排期是否已取消/已满员/已过期
  - 校验是否重复预约
```

#### cancel_booking — 取消预约

```yaml
name: cancel_booking
description: 取消当前用户的指定预约，自动校验是否在允许取消的时间窗口内
inputSchema:
  properties:
    booking_id: { type: integer, description: 预约ID }
  required: [booking_id]
权限: student
安全:
  - 只能取消自己的预约
  - 校验是否已签到/已完成（不可取消）
  - 校验是否在取消截止时间前
```

#### analyze_weekly_stats — 本周统计

```yaml
name: analyze_weekly_stats
description: 统计本周业务数据，包括预约量、到课率、热门课程、教师工作量
inputSchema:
  properties:
    week_offset: { type: integer, default: 0, description: 0=本周, -1=上周 }
权限: admin only
```

### 2.3 Tool 权限矩阵

| Tool | Student | Teacher | Admin |
|------|---------|---------|-------|
| query_courses / get_course_detail / query_schedules | ✅ | ✅ | ✅ |
| get_my_bookings / get_booking_detail | ✅（仅自己） | ✅（仅自己学生） | ✅ |
| get_my_balance / get_consumption_history | ✅（仅自己） | ❌ | ✅ |
| get_teacher_today | ❌ | ✅（仅自己） | ✅ |
| create_booking / cancel_booking / request_leave | ✅ | ❌ | ✅ |
| check_in | ❌ | ✅（仅自己课程） | ✅ |
| analyze_weekly_stats / analyze_popular_courses / analyze_teacher_workload | ❌ | ❌ | ✅ |

---

## 三、自然语言到业务操作流程设计

### 3.1 完整 Workflow

以用户输入 **"帮我预约明天下午的芭蕾课"** 为例：

```
Step 1: 用户输入 — "帮我预约明天下午的芭蕾课"

Step 2: Intent 识别（LLM）
  → intent: "create_booking", confidence: 0.95
  → "帮我预约" 明确表达了创建意图，不是查询

Step 3: 参数抽取（LLM Function Calling）
  → 时间: "明天" → 2026-08-06
  → 时段: "下午" → 14:00-18:00
  → 关键词: "芭蕾"
  → 但 create_booking 需要 schedule_id，不是模糊描述！
  → 需要先查排期，再创建预约

Step 4: 多 Tool 编排（ReAct Loop）
  Round 1: query_schedules(date="2026-08-06", keyword="芭蕾")
    → [ID:101 芭蕾形体 14:00-15:30, ID:102 芭蕾进阶 16:00]
  Round 2: Agent 反问用户确认
    → "找到 2 个芭蕾课：14:00 芭蕾形体、16:00 芭蕾进阶，您想预约哪个？"
  Round 3: 用户说"第一个"
    → create_booking(schedule_id=101) → "预约成功！"

Step 5: 业务校验（MCP Server 内部）
  ✅ 排期存在且未取消 / ✅ 排期未过期 / ✅ 剩余名额 > 0
  ✅ 用户未重复预约 / ✅ 用户未被禁用

Step 6: 数据写入
  BookingService.create_booking(user_id=42 ← 自动注入, schedule_id=101)

Step 7: 回复生成（LLM 润色）
  "预约成功！🎉 芭蕾形体 8月6日 周四 14:00-15:30 张老师 A教室
   温馨提示：开课前90分钟可自助取消～"
```

### 3.2 多 Tool 编排示例

```
场景："我这个月上了多少节课？"
  Round 1: get_my_balance() → { total: 30, consumed: 12, remaining: 18 }
  LLM 润色 → "您本月已消耗 12 课时，剩余 18 课时，大约还能上 2 周哦～"

场景："本周报名最多的课程是什么？"
  Round 1: analyze_weekly_stats() → 热门课程 Top 3
  LLM 润色 → "本周最受欢迎的是瑜伽基础课（42人次），其次是街舞初级（35人次）"
```

---

## 四、Agent 能力边界设计

### 4.1 适合交给 Agent 的能力

| 能力 | 原因 | 风险 |
|------|------|------|
| ✅ 查询课程/排期 | 只读，无副作用 | 低 |
| ✅ 查询个人预约/课时 | 只读，用户只能查自己 | 低 |
| ✅ 创建预约 | 有写入，但有严格校验 | 中 |
| ✅ 取消预约 | 有写入，但有限制条件 | 中 |
| ✅ 请假申请 | 有写入，但需审批 | 中 |
| ✅ 运营数据统计 | 只读聚合，管理员权限 | 低 |
| ✅ FAQ 问答 | 纯知识检索，无副作用 | 低 |

### 4.2 必须保留传统接口的能力

| 能力 | 原因 |
|------|------|
| ❌ 支付/充值 | 涉及资金安全，必须走微信支付原生流程 |
| ❌ 退款 | 资金操作必须人工确认 |
| ❌ 修改系统配置 | 误操作影响大（课程价格、角色权限等） |
| ❌ 删除核心数据 | 不可逆操作（课程、用户、排期） |
| ❌ 创建/修改用户 | 身份安全（注册、修改密码、绑定手机号） |
| ❌ 批量操作 | Agent 误解意图后果严重 |
| ❌ 教师薪资/结算 | 财务数据，必须人工确认 |
| ❌ 权限分配 | 安全敏感操作 |

**核心原则**：**"可逆的、只影响自己的、有校验兜底的"** 交给 Agent；**"不可逆的、涉及资金的、影响他人的"** 保留传统接口。

---

## 五、权限和安全设计

### 5.1 用户身份传递链路

```
小程序端 → Agent Runtime → MCP Server
storage.get('token') → Authorization: Bearer xxx → JWT 解出 user_id, tenant_id, role
                                                       ↓
                                                  自动注入到每个 Tool 调用上下文
```

**关键设计**：`user_id`、`tenant_id`、`role` 由 MCP Server 从 JWT 中解析并**自动注入**，**LLM 无权指定这些参数**。

### 5.2 防止 Agent 越权调用

| 防护层 | 措施 |
|--------|------|
| Tool 粒度控制 | 只暴露安全的 Tool，不暴露 delete/update/refund 等危险操作 |
| 参数注入 | user_id、tenant_id 由 MCP Server 从 JWT 解析注入，不接受 LLM 传参 |
| 角色校验 | 每个 Tool 调用前检查 ctx.user_role，不符合直接拒绝 |
| 租户隔离 | 所有查询自动带 tenant_id 过滤，无法跨租户访问数据 |
| 操作审计 | 所有 Agent 发起的操作记录日志，标记 source: "agent" |
| 频率限制 | Agent 调用频率限制比普通 API 更严格（防止 LLM 死循环重复调用） |

---

## 六、技术实现方案

### 6.1 推荐技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| MCP Server | Python + mcp SDK | 与现有 FastAPI 同语言，直接 import Service 层 |
| MCP 传输协议 | stdio（开发）/ SSE（生产） | stdio 简单，SSE 支持 HTTP 远程调用 |
| LLM | GPT-4o-mini（日常）/ Claude 3.5 Sonnet（复杂推理） | 性价比和能力平衡 |
| Agent 框架 | **不推荐 LangChain**，推荐原生 Function Calling | LangChain 抽象层太厚，调试困难；原生 API 更可控 |
| 会话管理 | Redis（已有） | 存储对话历史，支持多轮上下文 |
| 向量数据库 | Milvus Lite（开发）/ Milvus Standalone（展示） | 可选 RAG 场景 |
| Embedding | OpenAI text-embedding-3-small | 性价比高，1536 维，中文效果好 |

### 6.2 为什么不用 LangChain

| 维度 | LangChain | 原生 Function Calling |
|------|-----------|----------------------|
| 学习成本 | 高（Agent、Chain、Tool、Memory 多个概念） | 低（一个 API 调用） |
| 调试难度 | 黑盒，出错不知道哪层的问题 | 透明，每一步都可打断点 |
| 灵活性 | 框架约束多，定制困难 | 完全自由 |
| 依赖 | 重量级，安装慢 | 零依赖（httpx 即可） |
| 面试价值 | "我用了 LangChain"（套框架） | "我手写了 Agent 编排逻辑"（展示能力） |

### 6.3 目录结构

```
apps/api/src/app/ai/
├── __init__.py
├── mcp_server.py              # MCP Server 入口，注册所有 Tool
├── context.py                 # ToolContext: user_id, tenant_id, role
├── tools/
│   ├── query_courses.py       # 查询类 Tool
│   ├── query_schedules.py
│   ├── get_my_bookings.py
│   ├── get_my_balance.py
│   ├── get_teacher_today.py
│   ├── create_booking.py      # 操作类 Tool
│   ├── cancel_booking.py
│   ├── check_in.py
│   └── analyze_stats.py       # 分析类 Tool
├── agent/
│   ├── runtime.py             # Agent Runtime: 对话循环、多 Tool 编排
│   ├── intent.py              # Intent 识别
│   └── session.py             # 会话管理（Redis）
├── auth/
│   └── middleware.py           # Tool 鉴权中间件
└── rag/                       # 可选 RAG 模块
    ├── embedder.py            # FAQ 向量化
    └── retriever.py           # 向量检索
```

---

## 七、开发阶段规划

| Phase | 内容 | 工时 | 核心产出 |
|-------|------|------|----------|
| **Phase 1** | MCP Server 基础骨架 | 1 天 | query_courses / query_schedules / get_my_bookings 三个 Tool 可调通 |
| **Phase 2** | 查询类 Agent | 1 天 | Agent Runtime + 会话管理 + 补全查询类 Tool |
| **Phase 3** | 业务操作 Agent | 1 天 | create_booking / cancel_booking + 多 Tool 编排（ReAct Loop） |
| **Phase 4** | 复杂 Workflow + 分析 | 1 天 | 分析类 Tool + 小程序端 AI 对话组件 + 可选 RAG 知识库 |
| **Phase 5** | 生产环境优化 | 1 天 | SSE 传输协议 + 频率限制 + Token 成本监控 + 错误降级 |

**总计：约 5 天（35h）**

---

## 八、风险分析

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| LLM 返回格式不稳定 | Tool 调用失败 | 中 | 重试机制 + 降级到传统界面 |
| LLM 幻觉（编造课程/排期） | 用户误操作 | 低 | 所有 Tool 返回真实数据，LLM 只做润色 |
| Token 成本超预期 | 运营成本增加 | 中 | 使用 GPT-4o-mini 控制成本，设置每日上限 |
| 用户输入歧义 | 预约了错误的课程 | 中 | 关键操作前必须确认，用户说"是"才执行 |
| Agent 死循环 | 资源浪费 | 低 | 设置最大轮次（5轮），超时自动终止 |
| 隐私泄露 | 跨租户数据泄露 | 极低 | tenant_id 自动注入，LLM 不可修改 |

---

## 九、进阶：从 Agent 到 Agentic

### 9.1 核心区别

**"Agentic"** 形容的是 Agent 的**自主性程度**，是一条光谱而非独立技术：

```
被动响应 ←────────────────────────────────→ 主动自主
   │                                              │
  Agent（低自主性）                        Agentic（高自主性）
  "帮我查明天的课"                          "明天有新课，自动提醒学员"
  "帮我预约"                               "检测到学员3周没来，主动关怀"
  "本周数据怎么样"                          "每周一自动生成运营周报"
```

| 维度 | Agent（当前方案） | Agentic（升级方向） |
|------|---------------------|------------------------|
| 触发方式 | 用户发消息 → 执行 | 事件驱动 / 定时任务 → 自主执行 |
| 决策权 | 关键操作需用户确认 | 在安全边界内自主决策 |
| 记忆 | 多轮对话上下文 | 长期用户画像 + 行为模式 |
| 规划 | 单次任务编排 | 多目标、多步骤、跨天规划 |
| 错误恢复 | 失败后告知用户 | 失败后自动重试、换方案 |

### 9.2 本项目可落地的 Agentic 场景

当前 MCP Server + Function Calling 已是 Agentic 的地基，叠加 3 个能力即可升级：

**1. 定时触发 + 主动执行**

```python
@schedule(cron="0 10 * * *")  # 每天 10:00
async def auto_notify_today_courses():
    for user in get_users_with_booking_today():
        await agent.send_message(user_id=user.id,
            message=f"📅 提醒：您今天 {user.course_time} 有 {user.course_name} 课哦～")
```

**2. 长期记忆 + 用户画像**

```python
user_profile = {
    "favorite_courses": ["瑜伽", "芭蕾"],
    "usual_time": "evening",
    "attendance_rate": 0.85,
}
if user_profile["attendance_rate"] < 0.5:
    await agent.send_message(user_id, "最近是不是太忙了？这周有新课，要来试试吗？😊")
```

**3. 自主决策 + 安全边界**

```python
AUTO_APPROVE = ["query_courses", "get_my_balance", "send_reminder"]  # 自动执行
NEED_CONFIRM = ["create_booking", "cancel_booking"]                   # 需确认
```

### 9.3 适合本项目的 Agentic 场景

| 场景 | 实现方式 | 面试亮点 |
|------|----------|----------|
| 📅 上课提醒 | 定时任务 + Agent 推送 | "Agent 主动感知排课，课前自动提醒" |
| 📊 周报自动生成 | 每周一调 analyze_weekly_stats → 推送管理群 | "管理员不用开后台，AI 每周自动汇报" |
| 🔔 流失预警 | 检测 3 周未上课 → 自动关怀消息 | "Agent 从被动服务升级为主动运营" |
| 🎯 智能推荐 | 用户画像 + 空位排期 → 主动推荐 | "不是用户找课，是课找用户" |
| 📉 异常检测 | 排期连续满员 → 建议增开 | "Agent 具备运营意识，不只是执行工具" |

### 9.4 面试金句

> "我在项目中实现了 Agentic 架构，区别于传统的被动 Agent。系统不只是'用户问什么我答什么'，而是具备主动感知能力——课前自动提醒、流失学员自动关怀、每周自动生成运营报告。核心是在 MCP Tool 基础上叠加了定时调度、用户画像和自主决策引擎，让 Agent 从'工具'进化为'助手'。"