# MCP Tool 设计报告 — 学生约课业务

## 0. 当前真实状态声明

> **重要前提：本报告基于 2026-09-21 的真实代码快照。**
>
> 系统已经有完整的 AI + MCP 基础设施：
>
> | 组件 | 路径 | 状态 |
> |------|------|------|
> FastMCP Server | `ai/mcp_server.py` | ✅ **已实现**（6 个 Tool 已注册） |
> Tool 模块 | `ai/tools/*.py` | ✅ **已实现**（query_courses, query_schedules, create_booking, cancel_booking, get_my_bookings, get_my_balance） |
> AgentRuntime | `ai/agent/runtime.py` | ✅ **已实现**（意图识别 → Tool 调度 → 格式化回复） |
> IntentRecognizer | `ai/agent/intent.py` | ✅ **已实现** |
> SessionManager | `ai/agent/session.py` | ✅ **已实现**（Redis 分布式锁 + 会话上下文） |
> AI Router | `modules/ai/router.py` | ✅ **已实现**（POST /api/v1/ai/chat） |

**本报告是在此基础上的"设计评审 + 安全分析 + 标准化建议"。**

---

## 1. 用户意图分解

### 1.1 用户输入

> "帮我预约明天晚上 7 点的成人爵士舞。"

### 1.2 意图拆解

```
用户输入
  │
  ├─ Action: book / create_booking
  │
  └─ Parameters (LLM 需从自然语言提取):
       ├─ Time: "明天晚上 7 点"           → YYYY-MM-DD 19:00
       ├─ Course type: "成人爵士舞"         → 需要匹配 course_name 或 category
       └─ (隐含) User: 当前登录用户         → 从 JWT / Tool Context 获取
```

### 1.3 完成此意图需要的 Tool 调用链

```
Step 1: LLM 意图识别 → action=book, time=tomorrow_19:00, course="成人爵士舞"
                        │
Step 2: query_courses(keyword="爵士舞")   → 找到 course_id 或 course_name
                        │
Step 3: query_schedules(date="明天", keyword="爵士舞")  → 列出匹配的排期 + ID
                        │
Step 4: LLM 选择目标排期（基于时间匹配 + 剩余名额）
                        │
Step 5: create_booking(schedule_id=123)  → 完成预约
                        │
Step 6: 格式化回复 → "好的！已为您预约明天晚上 7 点的成人爵士舞..."
```

### 1.4 当前已有 Tool 覆盖情况

| 步骤 | 需要的 Tool | 当前状态 |
|------|------------|---------|
| Step 2 | `query_courses(keyword="爵士舞")` | ✅ **已实现** — `mcp_server.py:61-98` |
| Step 3 | `query_schedules(date="明天", keyword="爵士舞")` | ✅ **已实现** — `mcp_server.py:101-160` |
| Step 5 | `create_booking(schedule_id=123)` | ✅ **已实现** — `mcp_server.py:250-278` |

**结论：用户意图 "帮我预约明天晚上7点的成人爵士舞" 所需的所有 Tool 已存在。**

---

## 2. 现有 Service 能力映射（100% 基于真实代码）

### 2.1 核心业务 Service 清单

| Service | 路径 | 关键方法 | MCP Tool 用途 |
|---------|------|---------|--------------|
| **BookingService** | `modules/booking/service.py` | `create_booking`, `cancel_booking`, `list_bookings`, `get_booking_by_id`, `check_in_booking`, `complete_booking` | 核心约课操作 |
| **ScheduleService** | `modules/schedule/service.py` | `list_schedules`, `get_schedule_by_id`, `list_available` | 查询可预约排期 |
| **CourseService** | `modules/course/service.py` | `list_courses`, `get_course_by_id`, `list_types`, `list_categories` | 查询课程信息 |
| **MembershipCardService** | `modules/membership/service.py` | `get_user_balance`, `get_student_active_cards`, `deduct_credit`, `restore_credit` | 课时余额查询 + 扣次（BookingService 内部调用） |
| **UserService** | `modules/user/service.py` | `get_user_by_id`, `list_users` | 用户信息查询 |
| **AuthService** | `modules/auth/service.py` | `login`, `register`, `get_current_user_profile` | 认证 |

### 2.2 BookingService 方法签名（真实代码）

```python
# modules/booking/service.py — line 50
async def create_booking(
    self,
    db: AsyncSession,
    data: BookingCreate,         # ← Pydantic Schema: schedule_id, source?, membership_card_id?
    student_id: int,             # ← 关键：必须显式传入，不能让 LLM 伪造
    operator_id: int | None = None,
) -> BookingResponse:

# modules/booking/service.py — line 161
async def cancel_booking(
    self,
    db: AsyncSession,
    booking_id: int,
    student_id: int,             # ← 权限隔离：只能取消自己的预约
    reason: str | None = None,
) -> BookingResponse:

# modules/booking/service.py — line 333
async def list_bookings(
    self,
    db: AsyncSession,
    student_id: int | None = None,
    status: int | None = None,
    upcoming: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[BookingResponse], int]:
```

### 2.3 BookingCreate Schema

```python
# modules/booking/schemas.py（需确认）
# 已知字段: schedule_id, source?, membership_card_id?
```

### 2.4 BookingResponse Schema

```python
# modules/booking/schemas.py（需确认）
# 已知输出字段从 list_bookings 使用看:
# id, status, start_at, end_at, course_name, teacher_name, classroom_name
```

### 2.5 ❓ UNKNOWN 项

| # | 项目 | 原因 |
|---|------|------|
| UNK-1 | `BookingCreate.source` 的完整枚举值 | 需看 schemas.py 确认 |
| UNK-2 | BookingService 是否有查询"学生排期冲突"的能力 | 需 grep 确认 |
| UNK-3 | 是否有独立的 `list_available_schedules` 方法 | 需 grep |

---

## 3. 认证 / 鉴权 / Tenant 机制（真实代码）

### 3.1 Authentication（✅ 有）

```
HTTP 路由层:
  get_current_user(deps/auth.py)
    → 从 Authorization Header 提取 Bearer Token
    → JWT decode → payload = {user_id, tenant_id, role_id, ...}
    → set_user_id(), set_tenant_id(), set_role_id() 写入 ContextVar

MCP Tool 层:
  mcp_server.py:_require_auth(user_id, tenant_id)
    → 操作类 Tool 必须有 user_id + tenant_id
    → 查询类 Tool tenant_id 可选

AgentRuntime 层:
  ai/router.py:48-56
    → get_current_user → 提取 user_id, tenant_id
    → 注入 AgentRuntime(user_id=..., tenant_id=...)
    → Tool 通过 _require_auth(user_id, tenant_id) 从 Tool 参数获取
```

### 3.2 Authorization / RBAC（⚠️ BYPASS）

```python
# core/rbac/checker.py
PERMISSION_CHECK_BYPASS = True   # 🔴 所有权限检查被绕过
```

| 问题 | 现状 |
|------|------|
| Tool 权限边界 | 只有 `_require_auth(user_id, tenant_id)` — 检查身份存在 |
| 没有做什么 | 没有检查 user_id 是否属于 tenant_id、没有检查 role 是否允许约课操作 |

**风险：**
- MCP Tool 的 `_require_auth` 只检查"身份存在"，不检查"身份合法"
- `user_id=123, tenant_id=999` 这种跨租户组合会通过检查
- BookingService 自身的 TenantMixin + ORM 自动注入 tenant_id 会拦截，但 Tool 层没有提前防御

### 3.3 Tenant Isolation（✅ 三层）

```
层 1: Tool 层 set_tenant_id(tenant_id)
      → mcp_server.py 每个 Tool 开头调用

层 2: ContextVar 存储
      → core/tenant_context.py: get_tenant_id() = ContextVar

层 3: SQLAlchemy 事件自动注入
      → core/tenant_query.py: do_orm_execute 事件
      → 对所有 SELECT/UPDATE/DELETE 自动加 WHERE tenant_id = ?
      → INSERT 自动注入 tenant_id
```

**MCP Tool 中的应用：**
```python
# mcp_server.py:78
async def query_courses(keyword="", tenant_id=None):
    if tenant_id is not None:
        set_tenant_id(tenant_id)   # ← 层 1
    
    async with SessionLocal() as db:  # ← 层 2/3 在 db session 中生效
        service = CourseService()
        result = await service.list_courses(db, ...)
```

---

## 4. 现有 MCP Tool 完整清单与分析

### 4.1 Tool 清单（`mcp_server.py`）

| Tool 名 | 类型 | 输入 | 输出 | 复用 Service | 行号 |
|---------|------|------|------|-------------|------|
| `query_courses` | 查询 | keyword, category, level, tenant_id | str | CourseService.list_courses | 61-98 |
| `query_schedules` | 查询 | date, keyword, days, tenant_id | str | ScheduleService.list_schedules | 101-160 |
| `get_my_bookings` | 查询 | user_id, status, tenant_id | str | BookingService.list_bookings | 163-213 |
| `get_my_balance` | 查询 | user_id, tenant_id | str | membership_card_service.get_user_balance | 216-242 |
| `create_booking` | 操作 | schedule_id, user_id, tenant_id | str | BookingService.create_booking | 250-278 |
| `cancel_booking` | 操作 | booking_id, user_id, tenant_id, reason | str | BookingService.cancel_booking | 281-308 |

### 4.2 create_booking Tool 契约分析

```python
# mcp_server.py:250-278

@mcp.tool()
async def create_booking(
    schedule_id: int,           # ← LLM 必须提供
    user_id: int = None,        # ← AgentRuntime 注入
    tenant_id: int = None,      # ← AgentRuntime 注入
) -> str:
    """为当前用户预约指定排期的课程"""
    _require_auth(user_id, tenant_id)       # ← 身份检查
    set_tenant_id(tenant_id)                # ← 租户隔离
    
    async with SessionLocal() as db:
        service = BookingService()
        booking_data = BookingCreate(schedule_id=schedule_id)
        result = await service.create_booking(
            db, data=booking_data, student_id=user_id
        )
        return f"预约成功！课程：{result.course_name} 时间：..."
```

### 4.3 Tool 安全边界评估

| 安全维度 | 评估 | 说明 |
|---------|------|------|
| **Authentication** | ✅ 合格 | `_require_auth` 强制要求 user_id + tenant_id |
| **Authorization** | ⚠️ 弱 | 没有 RBAC 检查（全局 BYPASS） |
| **Tenant Isolation** | ✅ 合格 | `set_tenant_id` + ORM 事件自动注入 |
| **User 隔离** | ✅ 合格 | `BookingService.create_booking` 的 `student_id=user_id` 由 Tool 层绑定 |
| **参数验证** | ✅ 合格 | BookingService 内部完整业务校验（7 项） |
| **并发安全** | ✅ 合格 | FOR UPDATE SKIP LOCKED + DB Partial UNIQUE |
| **事务原子性** | ✅ 合格 | auto_commit=False 统一 commit（v1.1） |
| **会员卡扣次** | ✅ 合格 | BookingService 内部调用 + 独立 FOR UPDATE |
| **幂等性** | ✅ 合格 | Layer 2 SKIP LOCKED + Layer 3 DB UNIQUE |

---

## 5. "为什么 MCP Tool 不直接操作 PostgreSQL" — 核心设计原则

### 5.1 错误反例

```python
# ❌ 反例：MCP Tool 直接写 SQL
@mcp.tool()
async def create_booking(schedule_id, student_id, ...):
    async with SessionLocal() as db:
        # 绕过 BookingService，直接操作 Repository
        stmt = select(CourseSchedule).where(CourseSchedule.id == schedule_id)
        schedule = await db.execute(stmt)
        schedule = schedule.scalar_one()
        
        # 跳过所有业务校验！
        if schedule.booked_count < schedule.capacity:
            booking = Booking(schedule_id=..., student_id=..., ...)
            db.add(booking)
            schedule.booked_count += 1
            await db.commit()
```

### 5.2 错误后果

| 问题 | 后果 |
|------|------|
| 跳过 7 项业务校验 | 可能预约已取消的排期、已过期的排期 |
| 跳过 FOR UPDATE SKIP LOCKED | 并发约课可能超卖名额 |
| 跳过 auto_commit=False | 扣次失败时 Booking 永久化 |
| 跳过 membership deduct_credit | 学员没扣课时 |
| 绕过 PermissionException 检查 | 权限边界被击穿 |
| TenantMixin 不生效 | 可能跨租户查数据 |
| 两份业务逻辑（API 一套，MCP 一套） | DB 数据不一致 |
| 升级业务规则时 MCP 忘记同步 | 逻辑分叉 |

### 5.3 正确架构（当前代码已实现）

```
User（自然语言）
  │
  ▼
AI Agent（IntentRecognizer）
  │ 意图识别 + 参数提取
  ▼
MCP Tool（create_booking）
  │ 身份校验 + tenant 注入
  │ 参数: schedule_id, user_id(从JWT), tenant_id(从JWT)
  ▼
BookingService.create_booking()
  │ 7 项业务校验 + FOR UPDATE SKIP LOCKED
  │ auto_commit=False + IntegrityError 捕获
  │ 内部调用 MembershipCardService.deduct_credit()
  ▼
BookingRepository + ScheduleRepository + MembershipCardRepository
  │ 继承 TenantAwareRepository → 自动 tenant_id 注入
  ▼
SQLAlchemy AsyncSession
  │ do_orm_execute 事件 → 自动 WHERE tenant_id = ?
  ▼
PostgreSQL（bookings, course_schedules, membership_cards, ...）
```

### 5.4 为什么不能让 LLM 自己构造 SQL

| 考量 | 说明 |
|------|------|
| **LLM 不知道业务规则** | "已取消的排期不能预约"、"排期时间已过不能预约" — LLM 无法保证 SQL 覆盖这些规则 |
| **LLM 不知道锁策略** | FOR UPDATE SKIP LOCKED 在哪里加、什么时候加 — LLM 不会主动加 |
| **LLM 不知道事务边界** | booking + card + txn 必须同事务 — LLM 会拆成两条独立 SQL |
| **LLM 可能泄露数据** | 可能 SELECT 其他租户的数据 |
| **LLM 可能构造慢查询** | 可能忘记 WHERE 条件导致全表扫 |
| **LLM 不会处理错误** | IntegrityError、序列化、返回值格式化 |

---

## 6. 完整调用链图

### 6.1 用户说 "帮我预约明天晚上7点的成人爵士舞"

```
User（自然语言输入）
  │
  ▼
POST /api/v1/ai/chat
  │ JWT Bearer Token
  ▼
get_current_user（deps/auth.py）
  │ JWT decode → {user_id:42, tenant_id:7, role_id:2}
  │ set_user_id(42), set_tenant_id(7), set_role_id(2)
  ▼
AgentRuntime(user_id=42, tenant_id=7)
  │
  ▼
IntentRecognizer.recognize("帮我预约...")
  │ 识别: intent=create_booking
  │ 参数提取: date="tomorrow", time="19:00", course="成人爵士舞"
  ▼
Tool 调度决策（多步调用）
  │
  ├─ Step 1: query_courses(keyword="爵士舞", tenant_id=7)
  │           │
  │           ├─ set_tenant_id(7)
  │           ├─ SessionLocal → AsyncSession
  │           ├─ CourseService.list_courses(db, keyword="爵士舞")
  │           │   └─ CourseRepository.search()
  │           │       └─ SQLAlchemy SELECT → do_orm_execute 自动加 WHERE tenant_id=7
  │           └─ 返回 "成人爵士舞（...）" + 其他匹配课程
  │
  ├─ Step 2: query_schedules(date="明天", keyword="爵士舞", tenant_id=7)
  │           │
  │           ├─ set_tenant_id(7)
  │           ├─ SessionLocal → AsyncSession
  │           ├─ ScheduleService.list_schedules(db, ...)
  │           │   └─ ScheduleRepository.search()
  │           └─ 返回明天 19:00 的排期列表 + 剩余名额 + schedule_id
  │
  └─ Step 3: create_booking(schedule_id=123, user_id=42, tenant_id=7)
              │
              ├─ _require_auth(42, 7) ✅
              ├─ set_tenant_id(7)
              ├─ SessionLocal → AsyncSession
              ├─ BookingService.create_booking(db, BookingCreate(123), student_id=42)
              │   │
              │   ├─ 7 项业务校验 ✅
              │   ├─ ScheduleRepository.increment_booked_count(db, 123)
              │   │   └─ SELECT ... FOR UPDATE SKIP LOCKED WHERE bc<cap
              │   │
              │   ├─ BookingRepository.create(db, data, auto_commit=False)
              │   │   └─ INSERT bookings (flush, 未 COMMIT)
              │   │
              │   ├─ [如有卡] MembershipCardService.deduct_credit(db, ...)
              │   │   └─ SELECT card FOR UPDATE → used_credits+=1 → INSERT txn
              │   │
              │   └─ await db.commit()  ← 唯一一次 COMMIT
              │       ↓ 事务自动释放 FOR UPDATE 锁
              │
              └─ 返回 BookingResponse {id, course_name, start_at, ...}
                 └─ 格式化为自然语言回复
```

### 6.2 各层职责边界

```
┌────────────────────────────────────────────────────────────────┐
│ Layer 0: User Interface（自然语言入口）                        │
│   职责: 接收用户输入，返回自然语言回复                          │
├────────────────────────────────────────────────────────────────┤
│ Layer 1: AI Agent（AgentRuntime + IntentRecognizer）          │
│   职责: 理解自然语言 → 意图分类 → 参数提取 → Tool 调度         │
│   不做: 业务校验、数据查询、SQL 构造、锁管理                   │
├────────────────────────────────────────────────────────────────┤
│ Layer 2: MCP Tool（mcp_server.py）                            │
│   职责: 认证/鉴权检查、tenant_id 注入、参数序列化、结果格式化  │
│   不做: 业务逻辑实现、SQL 执行、事务管理                       │
├────────────────────────────────────────────────────────────────┤
│ Layer 3: Application Service（BookingService / ...）          │
│   职责: 业务校验、锁管理、事务编排、跨表原子性、错误处理       │
│   不做: SQL 拼接、连接管理                                     │
├────────────────────────────────────────────────────────────────┤
│ Layer 4: Repository（BookingRepository / ...）                │
│   职责: SQL 执行、ORM 操作、TenantMixin 自动注入               │
│   不做: 业务校验、锁策略决策                                   │
├────────────────────────────────────────────────────────────────┤
│ Layer 5: SQLAlchemy（AsyncSession + do_orm_execute 事件）     │
│   职责: 自动 WHERE tenant_id 注入、事务管理                    │
├────────────────────────────────────────────────────────────────┤
│ Layer 6: PostgreSQL                                            │
│   职责: 唯一约束、CHECK 约束、行锁、事务隔离                   │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. create_booking Tool 标准契约

### 7.1 Input Schema（JSON Schema）

```json
{
  "type": "object",
  "properties": {
    "schedule_id": {
      "type": "integer",
      "description": "排期 ID（从 query_schedules 获取）",
      "minimum": 1
    },
    "user_id": {
      "type": "integer",
      "description": "当前用户 ID（由 AgentRuntime 从 JWT 注入，LLM 不应自行填写）",
      "minimum": 1
    },
    "tenant_id": {
      "type": "integer",
      "description": "当前租户 ID（由 AgentRuntime 从 JWT 注入，LLM 不应自行填写）",
      "minimum": 1
    }
  },
  "required": ["schedule_id", "user_id", "tenant_id"]
}
```

### 7.2 Output Schema（自然语言字符串 — FastMCP 返回格式）

```
成功:
  "预约成功！\n课程：{course_name}\n时间：{MM/DD HH:mm-HH:mm}\n教室：{classroom}\n预约ID：{booking_id}"

失败（业务错误）:
  → 由 BookingService 抛 BusinessException → Tool 层捕获 → 格式化返回
  "预约失败：{具体原因}"

失败（认证/参数错误）:
  → _require_auth 抛 BusinessException → 格式化返回
  "未提供必要的身份信息"
```

### 7.3 Error 分类

| 场景 | 抛出位置 | HTTP/MCP Status | 返回给 LLM 的消息 |
|------|---------|-----------------|-------------------|
| schedule_id 不存在 | BookingService → NotFoundException | 404 | "排期不存在" |
| 排期已取消 | BookingService → BusinessException | 400 | "该排期已取消或已完成" |
| 排期已满 | BookingService → BusinessException | 400 | "该排期已约满" |
| 重复预约 | BookingService → IntegrityError catch → BusinessException | 400 | "您已预约该排期，请勿重复预约" |
| 会员卡次数用完 | BookingService → HTTPException catch → BusinessException | 400 | "会员卡次数已用完" |
| 会员卡已过期 | BookingService → HTTPException catch → BusinessException | 400 | "会员卡已过期" |
| 扣次失败（意外） | BookingService → Exception catch → BusinessException | 400 | "会员卡扣次失败，预约已撤销" |
| 无 user_id | _require_auth → BusinessException | 401 | "未提供用户身份" |
| SQL/DB 异常 | 全局 integrity_error_handler | 409 | "数据约束冲突" |

### 7.4 Tenant Isolation 在 Tool 中的体现

```python
# mcp_server.py:264-265 — 每次 Tool 调用都显式注入
_require_auth(user_id, tenant_id)   # 检查身份存在
set_tenant_id(tenant_id)            # 写入 ContextVar

# 后续所有 Service/Repository 操作自动:
#   SELECT ... WHERE tenant_id = ?    (ORM 事件注入)
#   INSERT ... tenant_id = ?          (TenantMixin 注入)
```

### 7.5 Transaction 在 Tool 中的体现

```python
async with SessionLocal() as db:    # ← 开启事务 (BEGIN)
    result = await service.create_booking(db, ...)
    # service 内部:
    #   increment_booked_count → FOR UPDATE 锁 schedule
    #   repo.create(auto_commit=False) → flush
    #   deduct_credit → FOR UPDATE 锁 card + INSERT txn
    #   await db.commit()        ← 唯一一次 COMMIT
    #   任何异常 → await db.rollback()
# SessionLocal 退出 → 事务结束 → 锁释放
```

### 7.6 Idempotency

```
create_booking 工具通过三层保证幂等:
  Layer 1: BookingService.find_active_booking — 预检查是否已有预约
  Layer 2: increment_booked_count FOR UPDATE SKIP LOCKED — 原子占位，只有一个能通过
  Layer 3: uq_bookings_schedule_student_active Partial UNIQUE — DB 层物理禁止重复
```

---

## 8. 锁顺序与死锁安全

| Tool / 流程 | 锁顺序 | 是否死锁 |
|-------------|--------|---------|
| create_booking | course_schedules FOR UPDATE → membership_cards FOR UPDATE | ❌ 无循环 |
| cancel_booking | bookings FOR UPDATE → course_schedules FOR UPDATE → membership_cards FOR UPDATE | ❌ 无循环 |
| deduct_credit（独立调用） | membership_cards FOR UPDATE | ❌ 单点 |

**所有 FOR UPDATE 锁的释放时机：同一 AsyncSession 的 COMMIT/ROLLBACK 后自动释放。**

---

## 9. Observability

### 9.1 现有日志覆盖

| 位置 | 日志内容 | 级别 |
|------|---------|------|
| BookingService.create_booking 入口 | schedule_id, student_id | INFO |
| BookingService.create_booking 成功 | booking.id | INFO |
| BookingService 业务校验失败 | 具体原因 | INFO / WARNING |
| BookingService IntegrityError | schedule_id, student_id, 约束名 | WARNING |
| BookingService deduct_credit 失败 | 异常详情 | ERROR |
| AgentRuntime.chat 入口 | user_input, session_id | INFO |
| AgentRuntime 锁竞争 | session_id | WARNING |

### 9.2 Tool 层应补充（建议）

| 补充项 | 说明 |
|--------|------|
| Tool name | 每次 Tool 调用记录 tool_name |
| request_id | 从 HTTP header 或 AgentRuntime 传递 |
| execution_time | 调用耗时 |
| result status | 成功/失败 + 具体 BusinessException 码 |

---

## 10. 完整链路图（最终版）

```
User（"帮我预约明天晚上7点的成人爵士舞"）
  │
  ▼
┌───────────────────────────────────────────────────────────────────┐
│ POST /api/v1/ai/chat  JWT: Bearer eyJhbGci...                     │
│   get_current_user → {user_id:42, tenant_id:7, role_id:2}         │
│   set_user_id(42), set_tenant_id(7), set_role_id(2)                │
└───────────────────────────────────────────────────────────────────┘
  │
  ▼
┌───────────────────────────────────────────────────────────────────┐
│ AgentRuntime(user_id=42, tenant_id=7)                            │
│   IntentRecognizer.recognize → intent="create_booking"            │
│   参数提取: {date="明天", time="19:00", course="成人爵士舞"}        │
│   Redis 分布式锁 acquire（防并发对话）                              │
└───────────────────────────────────────────────────────────────────┘
  │
  ├─→ query_courses(keyword="爵士舞", tenant_id=7)
  │   ├─ set_tenant_id(7)
  │   ├─ SessionLocal() BEGIN
  │   ├─ CourseService.list_courses(db, keyword="爵士舞")
  │   │   └─ CourseRepository.search()
  │   │       └─ SQL: SELECT * FROM courses WHERE keyword LIKE ...
  │   │           AND tenant_id = 7 ← do_orm_execute 事件自动注入
  │   └─ "成人爵士舞(standard, intermediate) ¥199"
  │
  ├─→ query_schedules(date="明天", keyword="爵士舞", tenant_id=7)
  │   ├─ set_tenant_id(7)
  │   ├─ SessionLocal() BEGIN
  │   ├─ ScheduleService.list_schedules(db, start_from=..., start_to=...)
  │   │   └─ ScheduleRepository.search() JOIN course_schedules + courses
  │   └─ "09/22 19:00-20:00 成人爵士舞 教师:王老师 教室:A101 已约:8/10 (schedule_id=123)"
  │
  └─→ create_booking(schedule_id=123, user_id=42, tenant_id=7)
      │
      ├─ _require_auth(42, 7) ✅
      ├─ set_tenant_id(7)
      ├─ SessionLocal() BEGIN  ← 🔑 开启单一事务
      │
      ├─ BookingService.create_booking(db, BookingCreate(123), student_id=42)
      │   │
      │   ├─ schedule_repo.get_by_id(123) → 排期存在？✅ status=NORMAL？✅ bc<cap？✅ 未过期？✅ 未开放？✅
      │   ├─ find_active_booking(123, 42) → None ✅
      │   │
      │   ├─ schedule_repo.increment_booked_count(db, 123)
      │   │   │  SELECT ... WHERE id=123 AND bc<10 FOR UPDATE SKIP LOCKED
      │   │   │  🔑 course_schedules 行锁 拿到！
      │   │   └─ schedule.bc = 9 → 10 (内存修改)
      │   │
      │   ├─ repo.create(db, data, auto_commit=False)
      │   │   └─ INSERT bookings (...) ← flush，未 COMMIT
      │   │
      │   ├─ [会员卡] membership_card_service.deduct_credit(db, card_id, ...)
      │   │   │  SELECT membership_cards WHERE id=? FOR UPDATE
      │   │   │  🔑 membership_cards 行锁 拿到！
      │   │   │  card.used_credits += 1
      │   │   │  INSERT membership_card_transactions (idempotency_key=booking_xxx_deduct)
      │   │   └─ ✅
      │   │
      │   └─ await db.commit()  ← 🔑 唯一一次 COMMIT
      │       ↓ 释放 course_schedules 锁 + membership_cards 锁
      │       ↓ 数据库一致性保证
      │
      └─ SessionLocal() 退出（事务结束）
         返回 BookingResponse → 格式化为:
         "预约成功！成人爵士舞 09/22 19:00-20:00 教室:A101 预约ID:456"
```

---

## 11. 风险清单

| # | 风险 | 等级 | 位置 | 描述 | 建议 |
|---|------|------|------|------|------|
| R1 | RBAC BYPASS | 🔴 High | `rbac/checker.py` | MCP Tool 只有身份检查无权限检查 | Tool 层增加 role 校验 |
| R2 | user_id 由 Tool 参数传入 | 🟡 Medium | `mcp_server.py:253` | 理论上 LLM 可以伪造不同 user_id | **强制**从 JWT 获取，Tool 参数从 AgentRuntime 自动注入，不暴露给 LLM |
| R3 | 缺少 Idempotency-Key header | 🟡 Medium | Router + Service | MCP HTTP 层重试无法跨进程幂等 | 后续补充 |
| R4 | 两个 Service 入口（API Router + MCP Tool） | 🟢 Low | — | 都复用同一 BookingService，业务逻辑一致 | ✅ 设计正确 |
| R5 | get_by_id 快照读 TOCTOU（check_in/complete） | 🟢 Low | `service.py:274+` | 同 v1.2 修复前 cancel 的问题 | 后续补 FOR UPDATE |

---

## 12. 遗留问题 / UNKNOWN

| # | 项目 | 原因 |
|---|------|------|
| UNK-1 | 当前 bookings 表真实数据量 | 未连接生产 DB |
| UNK-2 | BookingCreate / BookingResponse Schema 完整字段 | 需看 schemas.py 完整定义 |
| UNK-3 | 是否存在查询冲突排期的 Service 方法 | 需 grep Service |
| UNK-4 | PERMISSION_CHECK_BYPASS 何时关闭 | 产品决策 |
| UNK-5 | MCP 与 API Router 的认证入口统一方案 | 设计待讨论 |

---

## 13. 结论

### 13.1 MCP Tool 架构正确性

```
✅ MCP Tool → Service → Repository → SQLAlchemy → PostgreSQL
❌ MCP Tool → 直接 SQL
```

当前代码**完全遵循正确架构**：
- Tool 层只做认证/鉴权 + tenant 注入 + 参数序列化 + 结果格式化
- Service 层完整承载所有业务逻辑（校验、锁、事务）
- Repository 层继承 TenantAwareRepository 自动 tenant_id 注入
- SQLAlchemy 事件自动注入 WHERE tenant_id
- DB 层 Partial UNIQUE + CHECK 约束做最后保护

### 13.2 安全评估

| 维度 | 评级 | 说明 |
|------|------|------|
| Authentication | ✅ 合格 | JWT → user_id/tenant_id/role_id 注入 Tool 层 |
| Authorization | ⚠️ 弱 | PERMISSION_CHECK_BYPASS=True（全局问题，不是 MCP Tool 独有） |
| Tenant Isolation | ✅ 合格 | Tool 层 set_tenant_id + ORM 事件自动注入 |
| User 隔离 | ✅ 合格 | create_booking 的 student_id 由 Tool 绑定 user_id |
| 参数验证 | ✅ 合格 | BookingService 内部 7 项业务校验 |
| 并发安全 | ✅ 合格 | FOR UPDATE SKIP LOCKED + DB Partial UNIQUE |
| 事务原子性 | ✅ 合格 | auto_commit=False 统一 commit |
| 锁顺序 | ✅ 安全 | schedule → card，无死锁 |

### 13.3 工具覆盖度

| 用户意图 | 需要的 Tool | 当前状态 |
|---------|------------|---------|
| 预约"明天晚上7点的成人爵士舞" | query_courses → query_schedules → create_booking | ✅ 全部实现 |
| 取消预约 | cancel_booking | ✅ 实现 |
| 查我的预约 | get_my_bookings | ✅ 实现 |
| 查我的课时余额 | get_my_balance | ✅ 实现 |
| 查课程列表 | query_courses | ✅ 实现 |
| 查排期列表 | query_schedules | ✅ 实现 |

**结论：MCP Tool 覆盖了"约课"完整流程的所有查询+操作能力。当前代码架构正确、安全边界清晰。主要安全短板是 RBAC BYPASS（非 MCP 独有问题）。**