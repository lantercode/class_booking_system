# F5.1 — Acceptance Criteria

> 每条可独立判定 PASS / FAIL。主 AC 为 AC-3；全部 AC 通过方可进入 REVIEW。

## AC-1 统一格式输出（query_schedules）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-1.1 | 每个排期行以 `- ID:` 开头 | 代码审查 mcp_server.py + TC-01 |
| AC-1.2 | 含字段：ID、日期(YYYY-MM-DD)、时间(HH:MM-HH:MM)、教师、剩余名额、课程名 | TC-01 |
| AC-1.3 | 已满排期 `剩余:0`（`max(0, capacity - booked_count)`） | TC-01 |
| AC-1.4 | 无排期时返回 `{日期范围} 暂无排期`，不含 `- ID:` 行 | 代码审查 |

## AC-2 统一格式解析（_parse_schedules）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-2.1 | 解析出 `id(int)`、`date`、`time`、`teacher`、`remaining(int)`、`course_name` 六个字段 | TC-02 |
| AC-2.2 | 多行输入解析全部排期行，非 `- ID:` 行（标题/空行）被忽略 | TC-02 |
| AC-2.3 | 无排期文本返回空列表 `[]` | TC-02 |
| AC-2.4 | 正则与 query_schedules 输出格式严格匹配（同一示例字符串 round-trip） | TC-02 |

## AC-3 端到端预约流程（主验收标准）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-3.1 | 输入"预约明天的瑜伽课"→ 进入 create_booking 意图（非 query_schedules） | TC-03 |
| AC-3.2 | 第 1 轮返回排期选项列表（含"找到以下排期"、序号 `[1]`、课程名） | TC-03 |
| AC-3.3 | 第 2 轮回复"1"→ 调用 create_booking(schedule_id=解析出的 ID) 并返回"预约成功" | TC-03 |
| AC-3.4 | 预约成功回显包含解析出的 course_name（而非 keyword 兜底） | TC-03 |
| AC-3.5 | 预约后 session state 清除，后续对话不被误判为排期选择 | TC-03 |

## AC-4 意图识别配套修正

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-4.1 | "预约明天的瑜伽课" → create_booking（新增"预约"关键词） | TC-03 |
| AC-4.2 | "可以预约" / "可以约" / "可预约" → query_schedules（不误判为下单） | TC-04 |
| AC-4.3 | "我的预约" → get_my_bookings；"取消预约" → cancel_booking（优先级不变） | TC-04 |
| AC-4.4 | create_booking 提取 date 参数（"明天" → 明天日期） | TC-04 |

## AC-5 变更范围与静态质量

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-5.1 | 修改文件 ⊆ {mcp_server.py, runtime.py, intent.py, test_agent_runtime.py} | minimal-change-guard |
| AC-5.2 | 不改 Service 层（ScheduleService / BookingService） | diff 审查 |
| AC-5.3 | 不改 OpenAPI 契约（/ai/chat 请求/响应不变） | OpenAPI diff |
| AC-5.4 | 每个修改的 Python 文件通过 `python3 -m py_compile` | STATIC 记录 |
| AC-5.5 | 不引入未鉴权网络入口；Tool 仍只调 Service | 代码审查 |

## 判定规则

- AC-3 任一 FAIL → Feature 整体 FAIL。
- AC-1 / AC-2 / AC-4 任一 FAIL → NEEDS_FIX。
- AC-5 任一 FAIL → NEEDS_FIX（违反架构边界）。
