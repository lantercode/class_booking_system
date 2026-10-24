# F5.1 — Review

> 审查日期：2026-09-26
> 审查范围：F5.1 全部改动（mcp_server.py / runtime.py / intent.py / test_agent_runtime.py）

## 审查清单

### 功能正确性

| 项 | 结论 | 说明 |
|----|------|------|
| query_schedules 输出以 `- ID:` 开头 | PASS | L163-166 f-string |
| 六字段齐全（id/date/time/teacher/remaining/course_name） | PASS | 静态对照 + TC-01 |
| 已满排期 remaining=0 | PASS | `max(0, capacity - booked_count)` + TC-01 |
| _parse_schedules 正则与输出严格匹配 | PASS | round-trip 测试 |
| 无排期返回空列表不崩溃 | PASS | TC-02 |
| 多轮预约"预约明天的瑜伽课"→选"1"→成功 | PASS | TC-03 |
| 成功回显用解析出的 course_name | PASS | runtime.py L271 |

### 架构边界

| 项 | 结论 | 说明 |
|----|------|------|
| Tool 只调 Service，不直连 Repository/DB | PASS | query_schedules → ScheduleService.list_schedules |
| 不改 Service 层 | PASS | ScheduleService / BookingService 未动 |
| 不改 OpenAPI 契约 | PASS | /ai/chat router 未动 |
| 不引入未鉴权网络入口 | PASS | FastMCP stdio |
| 租户隔离未绕过 | PASS | set_tenant_id / _require_auth 保留 |

### 安全

| 项 | 结论 | 说明 |
|----|------|------|
| 四关校验顺序未变 | PASS | Authentication/Tenant 校验保留 |
| 输出不泄露内部异常 | PASS | _handle_business_error 未改（F5.3 已合规） |
| PII 最小化 | PASS | 排期展示无手机号等敏感字段 |
| 写操作仍需用户确认 | PASS | 多轮选择即确认环节，UI 侧不变 |

### 意图识别回归

| 项 | 结论 | 说明 |
|----|------|------|
| "预约"加入 create_booking | PASS | 覆盖用户主话术 |
| "可以预约"不误判为下单 | PASS | _match_intent 前置拦截 |
| 既有意图优先级不变 | PASS | get_my_bookings / cancel_booking 在 create_booking 前 |

## 风险与遗留

| 项 | 等级 | 处置 |
|----|------|------|
| 教师/课程名含 `\|` 致正则错位 | 低 | 当前数据不含；如需支持可后续转义 |
| "今天天气怎么样"被"今天"误判 query_schedules | 低 | 既有问题，不在 F5.1 范围 |
| 两端格式未来漂移 | 中 | 测试用同一示例 round-trip 锁定；注释标注耦合关系 |

## 结论

PASS。F5.1 改动最小、边界清晰、测试覆盖格式对齐与端到端流程，可进入发布。
