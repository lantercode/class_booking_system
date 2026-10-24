# F5.1 — 多轮预约流程修复 · 实现报告

> Feature ID：F5.1
> 完成日期：2026-09-26
> 状态：IMPLEMENTED

## 实现摘要

按统一格式对齐 `query_schedules` 输出与 `_parse_schedules` 解析，并配套修正意图识别使"预约明天的瑜伽课"可触发预约分支。未改 Service 层、未改 OpenAPI 契约、未改前端。

## 变更文件清单

| 文件 | 变更位置 | 变更内容 |
|------|---------|---------|
| `apps/api/src/app/ai/mcp_server.py` | `query_schedules`（约 L148-167） | 排期行格式改为 `- ID:{id} \| {date} \| {time} \| {teacher} \| 剩余:{remaining} \| {course_name}` |
| `apps/api/src/app/ai/agent/runtime.py` | `_parse_schedules`（约 L461-504） | 正则适配统一格式，新增 `course_name` 解析字段 |
| 同上 | `_format_schedule_options`（约 L506-519） | 展示 `{course} {teacher}（剩余N个）` |
| 同上 | `_handle_pending_state`（约 L269-276） | 成功回显课程名用 `selected_schedule['course_name']` |
| `apps/api/src/app/ai/agent/intent.py` | `INTENTS` create_booking（L32） | 新增关键词 `"预约"` |
| 同上 | `_match_intent`（L90-101） | 前置判断"可以预约/可以约/可预约"→ query_schedules |
| 同上 | `_extract_params`（L112） | date 提取条件扩展到 create_booking |
| `apps/api/tests/test_agent_runtime.py` | 新增 2 个测试函数 | `test_parse_schedules_unified_format`、`test_booking_flow_end_to_end` |

## 关键代码片段

### 统一格式（mcp_server.py）

```python
for s in result.items:
    date_str = s.start_at.strftime("%Y-%m-%d") if s.start_at else "待定"
    if s.start_at and s.end_at:
        time_str = f"{s.start_at.strftime('%H:%M')}-{s.end_at.strftime('%H:%M')}"
    else:
        time_str = "待定"
    teacher = s.teacher_name or "待定"
    remaining = max(0, s.capacity - s.booked_count)
    course_name = s.course_name or "未知课程"
    lines.append(
        f"- ID:{s.id} | {date_str} | {time_str} | {teacher} "
        f"| 剩余:{remaining} | {course_name}"
    )
```

### 解析正则（runtime.py）

```python
pattern = (
    r"ID:(\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d:-]+)\s*\|\s*"
    r"(.+?)\s*\|\s*剩余:(\d+)\s*\|\s*(.+?)\s*$"
)
```

## 未改动声明

- Service 层（`ScheduleService` / `BookingService`）未改动。
- `apps/api/src/app/modules/ai/router.py`（chat 契约）未改动。
- 前端 4 端未改动（chat 契约不变）。
- 未新增 Repository 访问、未裸 SQL、未直连 Redis 做业务读写。

## 安全合规

- Tool 仍只调 Service，符合 `ai/mcp.md`。
- 四关校验（认证/授权/租户/入参）未变更：`query_schedules` 仍走 `set_tenant_id`，`create_booking` 仍走 `_require_auth`。
- 无新增网络入口（FastMCP 仍 stdio）。
- 输出不泄露内部异常（`_handle_business_error` 未改动，已在 F5.3 合规）。

## 回归影响

- `query_schedules` 输出格式变化仅影响 `_parse_schedules` 消费者；`query_schedules` 意图的直接展示（`_format_schedules`）仍把原始文本包一层前缀，不解析，因此用户直接查排期时看到的新格式更结构化，无功能回退。
- 意图识别新增"预约"关键词：经回归测试，"我的预约"→get_my_bookings、"取消预约"→cancel_booking 优先级不变（前者在 create_booking 之前匹配）。
