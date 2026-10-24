# F5.1 — 多轮预约流程修复 · 实施方案

> Feature ID：F5.1
> 日期：2026-09-26
> 性质：格式对齐 + 意图配套修正，不改 Service / 契约 / 前端
> 关联文档：[requirement.md](./requirement.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

### 问题 1：query_schedules 与 _parse_schedules 格式不匹配

- `mcp_server.py` `query_schedules` 输出：`- {MM/DD HH:MM}-{HH:MM} {课程名} 教师：{teacher} 教室：{classroom} {已满/已约}（排期ID: {id}）`
- `runtime.py` `_parse_schedules` 正则期望：`- ID:{id} | {YYYY-MM-DD} | {HH:MM-HH:MM} | {teacher} | 剩余:{remaining}`
- 正则 `ID:(\d+)` 永远匹配不到以日期开头的行 → `_parse_schedules` 恒返回空列表 → 预约流程卡死。

### 问题 2：意图识别不支持裸"预约"

- `create_booking` 关键词仅含"帮我预约/我要约/预定/报名"等，不含裸"预约"。
- "预约明天的瑜伽课"中的"明天"命中 `query_schedules` → 进入查询分支而非预约分支。
- 且 `create_booking` 不提取 date 参数，即使进入预约分支也查不到"明天"的排期。

---

## Unified Format（唯一事实格式）

```
- ID:{id} | {YYYY-MM-DD} | {HH:MM-HH:MM} | {teacher} | 剩余:{remaining} | {course_name}
```

示例：
```
- ID:42 | 2026-09-27 | 14:00-15:00 | 王老师 | 剩余:5 | 瑜伽课
```

字段来源（均来自 `ScheduleResponse`，无需改 Service）：

| 字段 | 来源 |
|------|------|
| id | `s.id` |
| date | `s.start_at.strftime("%Y-%m-%d")` |
| time | `f"{s.start_at:%H:%M}-{s.end_at:%H:%M}"` |
| teacher | `s.teacher_name or "待定"` |
| remaining | `max(0, s.capacity - s.booked_count)` |
| course_name | `s.course_name or "未知课程"` |

---

## Affected Files

| # | 文件 | 改动内容 |
|---|------|---------|
| 1 | `apps/api/src/app/ai/mcp_server.py` | `query_schedules` 按统一格式输出 |
| 2 | `apps/api/src/app/ai/agent/runtime.py` | `_parse_schedules` 正则适配（含 course_name）；`_format_schedule_options` 展示 course_name；`_handle_pending_state` 成功回显用 course_name |
| 3 | `apps/api/src/app/ai/agent/intent.py` | `create_booking` 新增"预约"关键词；`_match_intent` 提前拦截"可以预约"类查询；`create_booking` 提取 date |
| 4 | `apps/api/tests/test_agent_runtime.py` | 新增 `test_parse_schedules_unified_format` 与 `test_booking_flow_end_to_end` |

---

## Exact Fix

### 1. mcp_server.py — query_schedules 输出统一格式

- 删除原 `{start_time}-{end_time} {course} 教师：X 教室：Y {availability}（排期ID: N）` 格式。
- 改为 `- ID:{s.id} | {date} | {time} | {teacher} | 剩余:{remaining} | {course_name}`。
- `remaining = max(0, capacity - booked_count)`，已满为 0。
- 注释标注"必须与 runtime._parse_schedules 正则严格一致"。

### 2. runtime.py — 解析与展示

- `_parse_schedules` 正则新增第 6 组 `course_name`，行尾锚定 `$`。
- 返回 dict 增加 `course_name` 字段。
- `_format_schedule_options` 展示 `{course} {teacher}（剩余N个）`。
- `_handle_pending_state` 成功回显 `课程：{selected_schedule['course_name'] or state['keyword']}`。

### 3. intent.py — 意图配套

- `create_booking` 关键词列表增加 `"预约"`。
- `_match_intent` 在主循环前判断 `("可以预约","可以约","可预约")` → `query_schedules`，避免被"预约"提前截获。
- `_extract_params` 中 date 提取条件从 `query_schedules` 扩展为 `("query_schedules", "create_booking")`。

---

## Why This Fix Is Sufficient

1. 两端用同一个格式字符串约束，正则与 f-string 逐字段对应，测试用同一示例做 round-trip 验证。
2. 不改 Service 层：`ScheduleResponse` 已提供全部所需字段。
3. 不改契约：`/ai/chat` 输入输出不变，前端无感。
4. 意图修正最小化：仅加一个关键词 + 一个前置查询判断，不重写识别器。

---

## Verification Plan

| AC 编号 | 验证方式 |
|---------|---------|
| AC-1 | `test_parse_schedules_unified_format` + 代码审查 |
| AC-2 | `test_parse_schedules_unified_format` round-trip |
| AC-3 | `test_booking_flow_end_to_end`（mock Tool + FakeRedis） |
| AC-4 | `test_intent_recognizer` + 专项断言 |
| AC-5 | `py_compile` + diff 审查 |

---

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 教师/课程名含 `\|` 字符 | 当前数据不含；正则用非贪婪匹配到固定分隔符 `剩余:`，若未来出现需转义 |
| U2 | "今天天气怎么样"被"今天"误判为 query_schedules | 既有问题，不在 F5.1 范围；不影响预约主流程 |
