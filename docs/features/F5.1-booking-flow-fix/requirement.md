# F5.1 — 多轮预约流程修复 · Requirement

> Feature ID：F5.1（Epic 5 / Phase 1 / P1）
> 阶段：REQUIREMENT（2026-09-26）

## Goal

AI 能正确解析排期列表并完成预约。用户说"预约明天的瑜伽课"时，AI 能列出可选排期，用户选择序号后完成预约。

## Problem

`query_schedules`（`apps/api/src/app/ai/mcp_server.py`）的输出格式与 `_parse_schedules`（`apps/api/src/app/ai/agent/runtime.py`）的解析格式**完全不匹配**，导致多轮预约流程卡死：

| 侧 | 实际/期望格式 |
|----|-------------|
| query_schedules 输出 | `- 09/14 14:00-15:00 瑜伽课 教师：王老师 教室：A教室 已约：2/10（排期ID: 5）` |
| _parse_schedules 期望 | `- ID:5 \| 2026-08-14 \| 14:00-15:00 \| 王老师 \| 剩余:3` |

`_parse_schedules` 的正则 `ID:(\d+) ...` 永远匹配不到以 `- 09/14` 开头的行 → 永远返回空列表 → `create_booking` 意图无 `schedule_id` 时拿不到排期选项 → 用户无法选择 → 预约流程中断。

此外，意图识别器 `create_booking` 关键词不含裸"预约"，"预约明天的瑜伽课"会被"明天"命中为 `query_schedules`，无法进入预约分支（AC 要求该短语可触发预约）。

## Scope

1. 定义统一排期文本格式（含 ID、日期、时间、教师、剩余名额、课程名）。
2. `query_schedules` 按统一格式输出。
3. `_parse_schedules` 按统一格式解析；`_format_schedule_options` 使用解析字段展示。
4. 预约成功回显使用解析出的 `course_name`（而非模糊的 keyword）。
5. 意图识别：`create_booking` 支持裸"预约"触发，同时保留"可以预约"为查询意图；`create_booking` 提取日期参数。

## Out of Scope

- 不修改 `ScheduleService.list_schedules`（Service 层不变）。
- 不修改 OpenAPI 契约（`/api/v1/ai/chat` 请求/响应不变）。
- 不修改前端（MCP Tool 输出格式变化不传导到 chat 契约，前端无需改动）。
- 不引入 LLM 语义理解，仍用关键词规则。

## User Roles

学员（通过 AI 对话预约课程的终端用户）。

## Business Rules

1. 排期输出格式两端（query_schedules / _parse_schedules）必须严格一致，使用同一个示例验证。
2. 每行排期必须以 `- ID:` 开头，便于 `_parse_schedules` 定位。
3. `remaining = max(0, capacity - booked_count)`，已满时为 0。
4. 日期格式 `YYYY-MM-DD`，时间格式 `HH:MM-HH:MM`。
5. 写操作（create_booking）仍走 Service 层，Tool 层不直连 Repository。

## Dependencies

- 依赖 `ScheduleService.list_schedules` 返回的 `ScheduleResponse`（含 id/start_at/end_at/capacity/booked_count/course_name/teacher_name）。
- 无前置 Feature 阻塞。

## Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 未来修改 query_schedules 格式忘记同步 _parse_schedules | 中 | 两端用同一个格式示例注释；测试用例直接对该示例做 round-trip |
| 教师/课程名含 `\|` 导致正则切分错位 | 低 | 当前数据不含 `\|`；正则用非贪婪匹配到下一个固定分隔符 `剩余:` |
| 意图识别"预约"范围扩大误伤查询 | 低 | "可以预约/可以约/可预约"提前归入 query_schedules；get_my_bookings/cancel_booking 在 create_booking 之前匹配 |

## Acceptance Criteria（摘要）

- AC-1：query_schedules 输出每行以 `- ID:` 开头，含日期/时间/教师/剩余/课程名。
- AC-2：_parse_schedules 能从 query_schedules 输出解析出 id/date/time/teacher/remaining/course_name。
- AC-3：用户说"预约明天的瑜伽课"→ AI 列出排期 → 回复"1"→ 预约成功。
- AC-4：无排期时返回空列表并提示，不崩溃。
