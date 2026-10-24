# Phase 2: MCP Engineer Analysis

> **日期**: 2026-09-22
> **角色**: mcp-engineer

---

## 1. 现有 MCP Tool 契约分析

### 1.1 Tool 清单

| Tool | 类型 | 当前签名 | 返回类型 |
|------|------|---------|---------|
| `query_courses` | 查询 | (keyword, category, level, tenant_id) | str |
| `query_schedules` | 查询 | (date, keyword, days, tenant_id) | str |
| `get_my_bookings` | 查询 | (user_id, status, tenant_id) | str |
| `get_my_balance` | 查询 | (user_id, tenant_id) | str |
| `create_booking` | 操作 | (schedule_id, user_id, tenant_id) | str |
| `cancel_booking` | 操作 | (booking_id, user_id, tenant_id, reason) | str |

### 1.2 鉴权机制 (`mcp_server.py:42-53`)

```python
def _require_auth(user_id, tenant_id):
    if user_id is None:
        raise BusinessException("未提供用户身份")
    if tenant_id is None:
        raise BusinessException("未提供租户身份")
```

**当前状态**: 只检查非 None，不校验与 JWT 的一致性。
**实际安全**: ✅ AgentRuntime 从 JWT 硬注入 user_id/tenant_id（Python 代码直接传参，LLM 不参与）。

### 1.3 错误处理

| 错误场景 | 当前处理 | 是否充分 |
|---------|---------|---------|
| user_id=None | _require_auth 抛 BusinessException | ✅ |
| tenant_id=None | _require_auth 抛 BusinessException | ✅ |
| 无结果 | 返回 "暂无预约记录" / "暂无排期" | ✅ |
| Service 异常 | 未捕获 → 全局 error_handler | ⚠️ 应在 Tool 层捕获 |
| 参数类型错误 | FastMCP 自动校验 | ✅ |

---

## 2. 需要改动的 Tool 契约

### 2.1 get_my_bookings — 增加 upcoming 参数

#### 当前 Input Schema

```json
{
  "user_id": "int (required, injected by AgentRuntime)",
  "status": "str (optional: booked/cancelled/checked_in/completed/no_show)",
  "tenant_id": "int (required, injected by AgentRuntime)"
}
```

#### 改动后 Input Schema

```json
{
  "user_id": "int (required, injected by AgentRuntime)",
  "status": "str (optional: booked/cancelled/checked_in/completed/no_show)",
  "upcoming": "bool (optional, default=false — 只返回未来未完成的预约)",
  "tenant_id": "int (required, injected by AgentRuntime)"
}
```

#### 改动后 Output Schema

```
upcoming=True:
  "您还有 3 节课：\n- [已预约] 09/22 19:00 成人爵士舞 教师：王老师（预约ID: 456）\n- ..."

upcoming=False (默认):
  "共 10 条预约记录：\n- [已完成] 09/15 19:00 瑜伽（预约ID: 123）\n- ..."
```

#### 改动后 Error Schema

| 场景 | 返回 |
|------|------|
| user_id=None | "未提供用户身份" |
| 无预约 | "暂无预约记录" (upcoming=True 时改为 "您近期没有课程安排") |
| Service 异常 | "查询预约失败，请稍后重试" |

### 2.2 query_schedules — 标注已满排期

#### 当前 Output 格式

```
"09/22 至 09/29 共 5 个排期：
- 09/22 19:00-20:00 成人爵士舞 教师：王老师 已约：8/10（排期ID: 123）
- 09/23 19:00-20:00 瑜伽 教师：李老师 已约：10/10（排期ID: 124）  ← 已满但无标注"
```

#### 改动后 Output 格式

```
"09/22 至 09/29 共 5 个排期：
- 09/22 19:00-20:00 成人爵士舞 教师：王老师 已约：8/10（排期ID: 123）
- 09/23 19:00-20:00 瑜伽 教师：李老师 已满（排期ID: 124）  ← 标注已满"
```

#### 改动代码

```python
# 当前 (mcp_server.py:149-151)
for s in result.items:
    ...
    lines.append(f"- {start_time}-{end_time} {course_name} 教师：{teacher} 已约：{s.booked_count}/{s.capacity}（排期ID: {s.id}）")

# 改动后
for s in result.items:
    ...
    if s.booked_count >= s.capacity:
        spots = "已满"
    else:
        spots = f"已约：{s.booked_count}/{s.capacity}"
    lines.append(f"- {start_time}-{end_time} {course_name} 教师：{teacher} {spots}（排期ID: {s.id}）")
```

### 2.3 get_my_balance — 无需改动 ✅

当前返回格式已完整：
```
"您的课时余额：
总购买：50 课时
已消耗：12 课时
剩余：38 课时"
```

### 2.4 query_courses — 无需改动 ✅

---

## 3. System Prompt 设计

### 3.1 当前状态

❌ **不存在 System Prompt**。AgentRuntime 的 `chat` 方法直接将用户输入传给 IntentRecognizer，没有 LLM 角色约束。

### 3.2 需要创建的 System Prompt

```python
# ai/agent/prompts.py (新文件)

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
4. 如果查询无结果，给出友好建议
"""
```

### 3.3 System Prompt 注入方式

在 AgentRuntime 的 chat 方法中，将 SYSTEM_PROMPT 作为对话上下文的前置内容注入：

```python
# runtime.py — 改动后的 chat 方法
async def chat(self, user_input: str, session_id: str = None) -> str:
    # 意图识别（当前逻辑不变）
    intent_result = self.intent_recognizer.recognize(user_input)
    
    # 注入 System Prompt 到会话上下文
    await self.session.add_message(
        session_id, role="system", content=SYSTEM_PROMPT
    )
    await self.session.add_message(
        session_id, role="user", content=user_input
    )
    
    # 后续调用 Tool + 格式化回复...
```

**注意**: 当前 IntentRecognizer 是基于关键词匹配的（不是 LLM），所以 System Prompt 目前更多是**文档化和未来扩展**的作用。当后续接入 LLM 做意图识别时，System Prompt 会成为关键的安全边界。

---

## 4. Input Validation 分析

| Tool | 参数 | 验证方式 | 风险 |
|------|------|---------|------|
| get_my_bookings | user_id | _require_auth 非 None 检查 | ✅ AgentRuntime 硬注入 |
| get_my_bookings | status | dict.get() 映射，无效值返回 None | ✅ 安全 |
| get_my_bookings | upcoming | bool 类型，FastMCP 自动校验 | ✅ 安全 |
| query_schedules | date | datetime.strptime 解析，格式错误抛异常 | ⚠️ 应捕获并返回友好提示 |
| query_schedules | keyword | 传给 Service 做 LIKE 查询 | ✅ SQLAlchemy 参数化查询，无 SQL 注入风险 |
| query_schedules | days | int 类型，FastMCP 自动校验 | ✅ 安全 |
| get_my_balance | user_id | _require_auth 非 None 检查 | ✅ 安全 |

### 需要补充的验证

```python
# query_schedules — date 参数校验
if date:
    try:
        start_from = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return "日期格式错误，请使用 YYYY-MM-DD 格式"
```

---

## 5. Redis 参与分析

| 功能 | Redis 用途 | 本次改动是否影响 |
|------|----------|----------------|
| AI 会话管理 | SessionManager 存储对话历史 + 中间状态 | ❌ 不影响（现有逻辑不变） |
| AI 并发锁 | 防止同会话并发请求 | ❌ 不影响 |
| RBAC 权限缓存 | 权限集合缓存 | ❌ 不影响 |

**结论**: 本次改动不涉及 Redis 新增使用。

---

## 6. 改动文件清单

| # | 文件 | 改动 |
|---|------|------|
| 1 | `ai/mcp_server.py` | get_my_bookings 增加 upcoming 参数 + query_schedules 标注已满 + date 校验 |
| 2 | `ai/agent/prompts.py` | 新建 System Prompt |
| 3 | `ai/agent/runtime.py` | 透传 upcoming 参数 + 注入 System Prompt |
| 4 | `ai/agent/intent.py` | 增加关键词 + upcoming 参数提取 |
