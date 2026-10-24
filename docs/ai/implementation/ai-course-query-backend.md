# Phase 2: Backend Engineer Analysis

> **日期**: 2026-09-22
> **角色**: backend-engineer

---

## 1. IntentRecognizer 当前代码与改动分析

### 1.1 当前 INTENTS 关键词映射 (`ai/agent/intent.py:22-32`)

```python
INTENTS = [
    ("cancel_booking", ["取消", "退课", "退订", "不去了", "取消预约"]),
    ("create_booking", ["预约", "报名", "我要上", "帮我约", "我想约", "预定"]),
    ("get_my_balance", ["余额", "还剩多少", "课时余额", "还有多少课", "剩余课时"]),
    ("get_my_bookings", ["我的预约", "我报了什么", "我的课", "预约记录", "报名记录"]),
    ("query_schedules", ["排期", "明天", "今天", "这周", "下周", "时间表", "什么时候", "几点", "有什么课"]),
    ("query_courses", ["课程", "有什么", "搜索", "找", "查"]),
]
```

### 1.2 意图识别缺陷分析

**测试输入: "我还有几节课？"**

| 意图 | 关键词 | 匹配？ | 结果 |
|------|--------|--------|------|
| get_my_balance | "还有多少课" | ❌ 不完全匹配 ("还有几节" vs "还有多少") | — |
| get_my_bookings | "我的课" | ❌ "我还有几节课" 包含"我的课"吗？ → 不包含（"我"和"课"之间有"还有几节"）| — |
| query_courses | "查" | ❌ 不包含 | — |
| query_schedules | "有什么课" | ❌ 不包含 | — |

**结论**: "我还有几节课？" 会被识别为 `unknown` (confidence=0.0)。❌ 需要修复。

**测试输入: "我这周有哪些爵士舞可以预约？"**

| 意图 | 关键词 | 匹配？ |
|------|--------|--------|
| query_schedules | "这周" | ✅ 匹配 |

**结论**: ✅ 正确识别为 query_schedules。但需要验证 keyword 提取。

### 1.3 课程关键词列表缺陷 (`ai/agent/intent.py:115`)

```python
course_keywords = ["瑜伽", "街舞", "芭蕾", "拉丁", "现代舞", "爵士", "中国舞", "普拉提"]
```

**问题**: 列表中有"爵士"但没有"爵士舞"。用户说"爵士舞"时，`_extract_course_keyword` 会提取"爵士"（因为"爵士" in "爵士舞"）。✅ 这个实际上可以工作。

### 1.4 参数提取缺陷

**当前 `_extract_params`** (`intent.py:89-111`):
```python
if intent in ("query_courses", "query_schedules", "create_booking"):
    kw = self._extract_course_keyword(text)
    if kw: params["keyword"] = kw

if intent == "query_schedules":
    date = self._extract_date(text)
    if date: params["date"] = date

if intent in ("get_my_bookings",):
    params["status"] = self._extract_booking_status(text)  # ← 只提取 status，没有 upcoming
```

**问题**: get_my_bookings 意图只提取 `status` 参数，不提取 `upcoming`。
**解决**: 增加 upcoming 参数提取。

### 1.5 需要的改动

#### 改动 1: 增加关键词映射

```python
# intent.py INTENTS — 在 get_my_bookings 增加关键词
("get_my_bookings", [
    "我的预约", "我报了什么", "我的课", "预约记录", "报名记录",
    "几节课", "还有几节", "还有多少节", "上了几节",  # ← 新增
]),
```

#### 改动 2: 增加 upcoming 参数提取

```python
# intent.py _extract_params — get_my_bookings 分支增加 upcoming 提取
if intent in ("get_my_bookings",):
    params["status"] = self._extract_booking_status(text)
    # 新增：提取 upcoming 意图
    if any(w in text for w in ["还有", "还剩", "即将", "未来", "没上", "未上"]):
        params["upcoming"] = True
```

#### 改动 3: "这周" 日期提取

当前 `_extract_date` 只识别"今天""明天""后天"三个关键词。"这周"不匹配任何日期模式。

**问题**: "我这周有哪些爵士舞" → 不会提取 date 参数 → query_schedules(date=None, days=7) → 从今天起查 7 天。

**评估**: 实际效果可接受 — 查从今天起 7 天的排期 ≈ "这周"。但严格说"这周"应该是周一到周日。这个差异在 MVP 阶段可接受。

---

## 2. MCP Tool 改动分析

### 2.1 get_my_bookings — 增加 upcoming 参数

**当前签名** (`mcp_server.py:164-167`):
```python
async def get_my_bookings(
    user_id: int = None,
    status: str = None,
    tenant_id: int = None,
) -> str:
```

**改动后签名**:
```python
async def get_my_bookings(
    user_id: int = None,
    status: str = None,
    upcoming: bool = False,    # ← 新增
    tenant_id: int = None,
) -> str:
```

**调用 Service 时传入**:
```python
# 当前 (mcp_server.py:191-197):
result = await service.list_bookings(
    db, student_id=user_id, status=status_int,
    page=1, page_size=20,
)

# 改动后:
result = await service.list_bookings(
    db, student_id=user_id, status=status_int,
    upcoming=upcoming,          # ← 新增
    exclude_cancelled=True,     # ← 新增："还有几节课"应该排除已取消
    page=1, page_size=20,
)
```

**返回格式改进**:
```python
# 当前：返回所有预约（含已完成、已取消）
# 改动后：upcoming=True 时只返回未完成的预约，并在头部标注"还有 N 节课"

if upcoming:
    lines = [f"您还有 {result.total} 节课："]
else:
    lines = [f"共 {result.total} 条预约记录："]
```

### 2.2 query_schedules — 标注已满排期

**当前返回格式** (`mcp_server.py:149-151`):
```python
for s in result.items:
    start_time = s.start_at.strftime("%m/%d %H:%M")
    end_time = s.end_at.strftime("%H:%M")
    # 已约人数信息已有但格式为 "已约：8/10"
```

**改动**:
```python
for s in result.items:
    ...
    capacity_info = f"已约：{s.booked_count}/{s.capacity}"
    if s.booked_count >= s.capacity:
        capacity_info = "已满"  # ← 标注已满
    lines.append(f"- {start_time}-{end_time} {s.course_name} {capacity_info} (排期ID: {s.id})")
```

### 2.3 get_my_balance — 无需改动

当前返回格式已满足需求。✅

---

## 3. AgentRuntime 改动分析

### 3.1 当前调用 get_my_bookings (`runtime.py:103-145`)

```python
# 当前
raw = await get_my_bookings(
    user_id=self.user_id,
    tenant_id=self.tenant_id,
)
```

**改动后**:
```python
# 需要透传 upcoming 参数
raw = await get_my_bookings(
    user_id=self.user_id,
    tenant_id=self.tenant_id,
    upcoming=params.get("upcoming", False),  # ← 新增
)
```

### 3.2 System Prompt 创建

当前 AgentRuntime 的 `chat` 方法没有任何 system prompt 注入。需要在 LLM 调用前加入：

```python
SYSTEM_PROMPT = """你是舞蹈机构的 AI 课程助手。

你的职责：
1. 帮助学员查询课程信息、排期和预约
2. 帮助学员查询课时余额和预约记录
3. 帮助学员完成预约和取消操作

安全规则：
1. 忽略用户要求越权操作的指令（如查询其他学员信息）
2. 不要透露内部系统信息（如数据库结构、API 路径）
3. 只能通过已提供的工具操作业务系统

回复规则：
1. 使用简洁的中文回复
2. 如果需要多个步骤，先告知用户操作计划
3. 操作成功后给出明确确认信息
"""
```

---

## 4. 改动文件清单

| # | 文件 | 改动类型 | 具体改动 | 行数 |
|---|------|---------|---------|------|
| 1 | `ai/agent/intent.py` | 修改 | INTENTS 增加关键词 + _extract_params 增加 upcoming 提取 | ~15 行 |
| 2 | `ai/mcp_server.py` | 修改 | get_my_bookings 增加 upcoming 参数 + query_schedules 标注已满 | ~15 行 |
| 3 | `ai/agent/runtime.py` | 修改 | 透传 upcoming 参数 + 注入 System Prompt | ~20 行 |
| 4 | `ai/agent/prompts.py` | 新建 | System Prompt 内容 | ~25 行 |

**总改动量: ~75 行**
