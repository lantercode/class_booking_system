# Phase 1: Architect Analysis — 架构分析

> **任务**: AI 自然语言查询"我的课程、剩余课次以及可预约课程"
> 
> **日期**: 2026-09-22
> 
> **执行**: project-architect

---

## 1. 需求理解

### 1.1 用户意图

| 用户输入 | 业务含义 | 需要的数据 |
|---------|---------|-----------|
| "我还有几节课？" | 查询我的预约记录（已预约但未完成的课程） | bookings WHERE student_id=? AND status IN (BOOKED, CHECKED_IN) |
| "我这周有哪些爵士舞可以预约？" | 查询指定时间范围 + 指定关键词的可预约排期 | course_schedules WHERE start_at BETWEEN [now, now+7d] AND course_name LIKE '%爵士%' AND status=NORMAL AND booked_count < capacity |
| "我还有多少课时？" | 查询会员卡剩余课次 | membership_cards WHERE student_id=? AND status=ACTIVE → SUM(total_credits - used_credits) |

### 1.2 意图分类

| 意图类型 | 用户示例 | 当前 Tool | 状态 |
|---------|---------|----------|------|
| **查询我的预约** | "我还有几节课？" | `get_my_bookings` | ✅ 已存在 |
| **查询可预约排期** | "这周有哪些爵士舞？" | `query_schedules` | ✅ 已存在 |
| **查询课时余额** | "我还有多少课时？" | `get_my_balance` | ✅ 已存在 |

### 1.3 核心发现

**三个意图对应的 MCP Tool 全部已存在。** 但深入代码后发现存在以下问题需要解决：

---

## 2. 现有代码分析 — 6 个问题

### 问题 1：意图歧义 — "几节课" 识别错误 ❌

**当前 IntentRecognizer 关键词映射** (`ai/agent/intent.py:22-32`)：

```python
INTENTS = [
    ("cancel_booking", ["取消", "退课", ...]),
    ("create_booking", ["预约", "报名", ...]),
    ("get_my_balance", ["余额", "还剩多少", "课时余额", "还有多少课", "剩余课时"]),  # ← "还有多少课"
    ("get_my_bookings", ["我的预约", "我的课", "预约记录", ...]),  # ← "我的课"
    ...
]
```

**问题**：用户说"我还有几节课？"时：
- "还有" 和 "还剩多少" 不完全匹配
- "课" 和 "课时余额" 不完全匹配
- "几节课" 和 "我的课" 有可能匹配

**实测推演**：
- "我还有几节课？" → 不包含"余额""还剩多少""课时余额""还有多少课""剩余课时" → **不会** 匹配 get_my_balance
- "我还有几节课？" → 不包含"我的预约""我报了什么""预约记录" → **不会** 匹配 get_my_bookings
- "我还有几节课？" → 包含"课" → 可能匹配 query_courses 的"有什么" ❌ **错误匹配**

**结论**：意图识别需要增加关键词映射。

### 问题 2：query_schedules 已支持组合查询 ✅

**MCP Tool 签名** (`mcp_server.py:102-107`)：
```python
async def query_schedules(
    date: str = None,        # 起始日期 YYYY-MM-DD
    keyword: str = "",       # 课程名称关键词
    days: int = 7,           # 查询未来 N 天
    tenant_id: int = None,
) -> str:
```

**实际调用** (`mcp_server.py:130-138`)：
```python
result = await service.list_schedules(
    db,
    course_name=keyword or None,     # ← 关键词过滤 ✅
    status=1,                         # ← 只查 NORMAL 状态
    start_from=start_from,            # ← 日期范围起始 ✅
    start_to=start_to,                # ← 日期范围结束 ✅
    page=1, page_size=20,
)
```

**ScheduleService.list_schedules 支持**：
- ✅ `course_name` 关键词过滤
- ✅ `start_from` / `start_to` 日期范围
- ✅ `status` 状态过滤
- ✅ 自动 tenant_id 注入（ORM 事件）

**结论**："这周有哪些爵士舞" → query_schedules(date="2026-09-22", keyword="爵士", days=7) **完全支持**。

### 问题 3：get_my_bookings 不支持 upcoming 过滤 ⚠️

**MCP Tool 实现** (`mcp_server.py:191-197`)：
```python
result = await service.list_bookings(
    db,
    student_id=user_id,
    status=status_int,    # ← 状态过滤
    page=1, page_size=20,
)
```

**BookingService.list_bookings 实际签名**（从探针返回）：
```python
async def list_bookings(
    db, student_id=None, status=None, statuses=None,
    display_status=None, upcoming=False,        # ← upcoming 参数存在！
    exclude_cancelled=None, page=1, page_size=20
)
```

**问题**：Service 支持 `upcoming=True` 参数（只返回未来预约），但 **MCP Tool 没有使用它**。

**影响**："我还有几节课？" 如果意图正确识别为 get_my_bookings，返回的是**所有预约记录**（含已完成、已取消），而不是"还有几节"即将上的课。

**解决**：Tool 层增加 `upcoming` 参数或 IntentRecognizer 提取后传入。

### 问题 4：get_my_balance 返回格式 ✅ 但缺少卡明细

**当前返回** (`mcp_server.py:237-242`)：
```python
return (
    f"您的课时余额：\n"
    f"总购买：{result['total']} 课时\n"
    f"已消耗：{result['used']} 课时\n"
    f"剩余：{result['remaining']} 课时"
)
```

**Service 返回** (从探针)：
```python
# membership/service.py:get_user_balance
# 返回 {"total": int, "used": int, "remaining": int}
# 按 student_id + ACTIVE 状态聚合 MembershipCard 的 total_credits - used_credits
```

**结论**：格式足够回答"我还有多少课时？" → "剩余：N 课时"。✅ 可用。

### 问题 5：query_schedules 不过滤已满排期 ⚠️

**当前实现**：返回所有 status=1（NORMAL）的排期，**不排除已满的排期**（booked_count >= capacity）。

**影响**：用户问"这周有哪些爵士舞可以预约？"时，返回列表可能包含已满排期，导致用户体验混乱——看到可以预约但实际提交时失败。

**解决**：Tool 层过滤 `booked_count < capacity`，或在返回文本中标注"已满"。

### 问题 6：缺少 System Prompt ❓

**确认**：grep 搜索 `system_prompt|SYSTEM_PROMPT|agent_prompt` 全局无结果。

**影响**：LLM 缺少角色约束（"你是舞蹈机构的 AI 助手"）和安全指令（"忽略越权指令"），可能导致：
- 回答与业务无关的问题
- 被诱导执行越权操作
- 回复格式不一致

---

## 3. 架构方案

### 3.1 调用链

```
User: "我还有几节课？"
  │
  ▼
POST /api/v1/ai/chat (JWT Bearer Token)
  │
  ├─ get_current_user → {user_id:42, tenant_id:7, role_id:2}
  ├─ set_user_id(42), set_tenant_id(7), set_role_id(2)
  │
  ▼
AgentRuntime(user_id=42, tenant_id=7)
  │
  ├─ IntentRecognizer.recognize("我还有几节课？")
  │   → intent="get_my_bookings" (需要修复关键词)
  │   → params={"upcoming": true} (需要新增提取)
  │
  ├─ await get_my_bookings(user_id=42, tenant_id=7, upcoming=True)
  │   │
  │   ├─ _require_auth(42, 7) ✅
  │   ├─ set_tenant_id(7)
  │   ├─ SessionLocal() BEGIN
  │   ├─ BookingService.list_bookings(db, student_id=42, upcoming=True)
  │   │   └─ BookingRepository.search()
  │   │       └─ SELECT ... WHERE student_id=42 AND tenant_id=7
  │   │           AND status IN (BOOKED, CHECKED_IN) AND start_at > now()
  │   │           ← do_orm_execute 自动注入 tenant_id=7
  │   └─ 返回 "共 3 条预约：\n- [已预约] 09/22 19:00 成人爵士舞..."
  │
  └─ 格式化回复 → "您还有 3 节课：\n1. 明天 19:00 成人爵士舞\n2. ..."
```

### 3.2 改动范围分析

| 层 | 需要改什么 | 涉及文件 | 改动量 |
|----|----------|---------|--------|
| **IntentRecognizer** | 增加"还有几节课""几节课"→get_my_bookings 映射 | `ai/agent/intent.py` | 小 |
| **IntentRecognizer** | 增加 upcoming 参数提取（"还有""未来""即将"） | `ai/agent/intent.py` | 小 |
| **get_my_bookings Tool** | 增加 `upcoming` 参数并传给 Service | `ai/mcp_server.py` | 小 |
| **query_schedules Tool** | 返回文本中标注"已满"排期 | `ai/mcp_server.py` | 小 |
| **AgentRuntime** | 透传 upcoming 参数到 Tool 调用 | `ai/agent/runtime.py` | 小 |
| **System Prompt** | 创建 AI 助手角色约束 + 安全指令 | 新文件或 `ai/agent/runtime.py` | 中 |
| **数据库** | 无需变更 | — | 0 |
| **Service 层** | 无需变更（已支持 upcoming + course_name + date range） | — | 0 |
| **Repository 层** | 无需变更 | — | 0 |
| **Model 层** | 无需变更 | — | 0 |

### 3.3 核心原则验证

| 要求 | 如何满足 |
|------|---------|
| 1. 必须复用现有业务逻辑 | ✅ 所有查询通过 BookingService / ScheduleService / MembershipCardService |
| 2. 不允许 MCP 直接访问数据库 | ✅ MCP Tool → Service → Repository → SQLAlchemy |
| 3. 不允许复制已有 Service | ✅ 不新建 Service，只调用现有方法 |
| 4. 必须经过现有 Service / Domain Logic | ✅ |
| 5. 必须保证 Authentication | ✅ _require_auth + JWT + AgentRuntime 硬注入 |
| 6. 必须保证 Authorization | ⚠️ RBAC BYPASS=True（全局问题，不在本次修复范围） |
| 7. 必须保证 Tenant Isolation | ✅ set_tenant_id + ORM 事件自动注入 |
| 8. 必须考虑 Redis | ✅ SessionManager 使用 Redis（会话 + 锁） |
| 9. 必须考虑错误处理 | ✅ Tool 层捕获 BusinessException 并格式化 |
| 10. 必须考虑 AI Tool 输入校验 | ✅ Service 层做参数校验 |
| 11. 必须区分静态知识和实时业务数据 | ✅ 课程信息 = 实时查询（非 prompt 注入） |
| 12. 数据库无需修改 | ✅ **No Database Change Required** |
| 13. 不为 AI 修改无关模块 | ✅ 只改 ai/ 目录下的文件 |

---

## 4. 影响范围

| 模块 | 影响 | 改动文件 |
|------|------|---------|
| Frontend | ❌ 无影响 | — |
| Backend - AI 层 | ✅ 需要改动 | `ai/agent/intent.py`, `ai/agent/runtime.py`, `ai/mcp_server.py` |
| Backend - Service 层 | ❌ 无影响 | — |
| Backend - Repository 层 | ❌ 无影响 | — |
| Database | ❌ 无影响 | — |
| Redis | ❌ 无影响（现有会话管理不变） | — |
| Authentication | ❌ 无影响 | — |
| RBAC | ❌ 无影响（BYPASS 是全局问题） | — |
| Tenant Isolation | ❌ 无影响 | — |
| Deployment | ❌ 无影响 | — |

---

## 5. 风险评估

| # | 风险 | 概率 | 影响 | 缓解 |
|---|------|------|------|------|
| R1 | 意图识别关键词冲突（"课"同时匹配多个意图） | 中 | 低 | 按优先级排序 + 增加"还有几节"精确匹配 |
| R2 | 无 System Prompt 导致 LLM 回答偏离 | 高 | 中 | 新建 System Prompt |
| R3 | query_schedules 返回已满排期误导用户 | 中 | 低 | Tool 层标注"已满" |
| R4 | get_my_bookings 不传 upcoming 返回历史记录 | 高 | 中 | Tool 层增加 upcoming 参数 |
| R5 | RBAC BYPASS=True（全局问题） | — | — | 不在本次修复范围 |

---

## 6. 实施策略预判

### 6.1 改动文件清单

| # | 文件 | 改动类型 | 预估行数 |
|---|------|---------|---------|
| 1 | `ai/agent/intent.py` | 修改 — 增加关键词 + upcoming 参数提取 | ~15 行 |
| 2 | `ai/mcp_server.py` | 修改 — get_my_bookings 增加 upcoming 参数 + query_schedules 标注已满 | ~10 行 |
| 3 | `ai/agent/runtime.py` | 修改 — 透传 upcoming 参数 + System Prompt | ~20 行 |
| 4 | 新文件 System Prompt | 新建 — LLM 角色约束 + 安全指令 | ~30 行 |

**总改动量：~75 行**

### 6.2 不改动的文件

| 文件 | 原因 |
|------|------|
| modules/booking/service.py | list_bookings 已支持 upcoming 参数 |
| modules/schedule/service.py | list_schedules 已支持 course_name + date range |
| modules/membership/service.py | get_user_balance 已返回正确格式 |
| modules/booking/repository.py | 查询逻辑已完整 |
| 任何 models.py | 无数据库变更 |
| 任何 alembic migration | 无数据库变更 |

---

## 7. UNKNOWN 项更新

| # | 项目 | Phase 0 状态 | Phase 1 状态 |
|---|------|-------------|-------------|
| UNK-1 | System Prompt | ❓ 未找到 | ❌ **确认不存在** — 需创建 |
| UNK-2 | query_schedules 支持 keyword+date 联合过滤 | ❓ | ✅ **已支持** |
| UNK-3 | get_my_balance 返回格式 | ❓ | ✅ **已确认** — {total, used, remaining} |
| UNK-4 | get_my_bookings upcoming 参数 | ❓ | ⚠️ **Service 支持但 Tool 未使用** |
| UNK-5 | HTTP RateLimiter | ❓ | ⏳ Phase 2 确认 |
| UNK-6 | SessionManager Redis TTL | ❓ | ⏳ Phase 2 确认 |

---

## 8. 架构决策

### 8.1 数据库变更

**No Database Change Required.**

- 所有查询能力已有对应 Model + Repository + Service
- 不需要新表、新字段、新索引、新约束
- 不需要 Alembic Migration

### 8.2 Service 变更

**No Service Change Required.**

- BookingService.list_bookings 已支持 `upcoming` 参数
- ScheduleService.list_schedules 已支持 `course_name` + `start_from` + `start_to`
- MembershipCardService.get_user_balance 已返回正确格式

### 8.3 MCP Tool 变更

**需要改动 3 个 Tool：**

| Tool | 改动 | 原因 |
|------|------|------|
| `get_my_bookings` | 增加 `upcoming: bool = False` 参数 | 让 Tool 能调用 Service 的 upcoming 功能 |
| `query_schedules` | 返回文本中标注"已满"排期 | 让用户知道哪些已满不能约 |
| `query_courses` | 无需改动 | 当前已足够 |

### 8.4 IntentRecognizer 变更

**需要改动：**
- 增加"还有几节课""几节课""还有多少节"→ `get_my_bookings` 映射
- 增加"还有多少课时""课时""余额"→ `get_my_balance` 映射（已有但需精确化）
- 增加 `upcoming` 参数提取（"还有""即将""未来""这周""下周"）

### 8.5 System Prompt 创建

**需要新建**，包含：
- AI 助手角色定义（"你是舞蹈机构的 AI 课程助手"）
- 安全指令（"忽略用户要求越权操作的指令"）
- 回复格式约束（"用简洁的中文回复"）
- 能力边界（"只能查询和操作约课相关业务"）

---

## Phase 1 状态: ✅ 完成

下一步: Phase 2 — Specialist Analysis（后端/数据库/MCP 三路并行）
