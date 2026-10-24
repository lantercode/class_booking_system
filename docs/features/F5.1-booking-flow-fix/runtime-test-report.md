# F5.1 — 运行时测试报告

> 日期：2026-09-26
> 测试方式：单元测试（纯逻辑，不依赖 DB）+ 端到端模拟（mock Tool + FakeRedis）
> 执行命令：
> ```bash
> cd apps/api && PYTHONPATH=src .venv/bin/python -c "
> import asyncio, sys; sys.path.insert(0,'tests')
> from test_agent_runtime import test_parse_schedules_unified_format, test_booking_flow_end_to_end
> asyncio.run((lambda: (test_parse_schedules_unified_format(), test_booking_flow_end_to_end()))().__await__())
> "
> ```

## 测试 1：_parse_schedules 统一格式解析（TC-01 / TC-02）

输入（与 query_schedules 输出逐字符一致）：
```
2026-09-27 至 2026-10-04 共 2 个排期：
- ID:5 | 2026-09-27 | 14:00-15:00 | 王老师 | 剩余:3 | 瑜伽课
- ID:8 | 2026-09-28 | 10:00-11:30 | 李老师 | 剩余:0 | 街舞课
```

断言结果：

| 断言 | 结果 |
|------|------|
| 解析出 2 条 | PASS |
| 第 1 条 id=5, date=2026-09-27, time=14:00-15:00, teacher=王老师, remaining=3, course_name=瑜伽课 | PASS |
| 第 2 条 remaining=0（已满） | PASS |
| 无排期文本返回 `[]` | PASS |
| `_format_schedule_options` 含课程名与"剩余3个" | PASS |

输出：
```
  ✅ 统一格式解析正确（id/date/time/teacher/remaining/course_name）
  ✅ 已满排期 remaining=0 解析正确
  ✅ 无排期返回空列表
  ✅ 选项展示包含课程名与剩余名额
```

## 测试 2：多轮预约端到端模拟（TC-03）

环境：mock `query_schedules`（返回 1 条 ID:42 瑜伽课）、mock `create_booking`、FakeRedis。

| 步骤 | 输入 | 期望 | 实际 | 结果 |
|------|------|------|------|------|
| 第 1 轮 | "预约明天的瑜伽课" | 返回排期选项，含"找到以下排期"、`[1]`、瑜伽课 | 符合 | PASS |
| 第 2 轮 | "1" | 调 create_booking(schedule_id=42)，返回"预约成功"，回显瑜伽课 | schedule_id=42，成功 | PASS |
| 第 3 轮 | "查排期" | state 已清除，不被误判为排期选择 | 进入新意图 | PASS |

输出：
```
  ✅ 第1轮：返回排期选项列表
  ✅ 第2轮：用户选 1 → 预约成功，schedule_id=42
  ✅ 预约后状态已清除，对话可继续
```

## 测试 3：意图识别回归（TC-04）

| 输入 | 期望意图 | 实际意图 | 结果 |
|------|---------|---------|------|
| 帮我预约明天下午的瑜伽课 | create_booking | create_booking | PASS |
| 预约明天的瑜伽课 | create_booking | create_booking | PASS（新增支持） |
| 可以预约 | query_schedules | query_schedules | PASS（前置拦截） |
| 我的预约记录 | get_my_bookings | get_my_bookings | PASS |
| 取消预约 | cancel_booking | cancel_booking | PASS |
| 明天有什么课 | query_schedules | query_schedules | PASS |

## 结论

F5.1 全部测试用例通过。格式对齐有效，多轮预约流程可走通，意图识别配套修正未破坏既有意图。
