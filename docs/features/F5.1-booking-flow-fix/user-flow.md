# F5.1 — 多轮预约流程修复 · User Flow

> 关联：[requirement.md](./requirement.md)

## 主流程：查排期 → 选排期 → 预约成功

```
用户                        AI Runtime                     Tool / Service
 │                             │                               │
 │ "预约明天的瑜伽课"          │                               │
 ├────────────────────────────►│                               │
 │                             │ intent=create_booking         │
 │                             │ (无 schedule_id)              │
 │                             ├──────────────────────────────►│ query_schedules(date=明天, keyword=瑜伽)
 │                             │                               │ ScheduleService.list_schedules
 │                             │◄──────────────────────────────┤ 统一格式排期列表
 │                             │ _parse_schedules → 存 state   │
 │  "找到以下排期，请回复数字" │                               │
 │◄────────────────────────────┤                               │
 │                             │                               │
 │ "1"                         │                               │
 ├────────────────────────────►│                               │
 │                             │ get_state → selecting_schedule│
 │                             │ _parse_user_selection → 1     │
 │                             ├──────────────────────────────►│ create_booking(schedule_id=42)
 │                             │                               │ BookingService.create_booking
 │                             │◄──────────────────────────────┤ 预约成功
 │                             │ clear_state                   │
 │  "✅ 预约成功！课程：瑜伽课"│                               │
 │◄────────────────────────────┤                               │
```

### 关键状态

| 阶段 | session state | 说明 |
|------|--------------|------|
| 第 1 轮后 | `{action: "selecting_schedule", schedules: [...], keyword, date}` | 等待用户选序号 |
| 第 2 轮成功后 | 清除 | 预约完成，对话可继续 |

## 分支 1：无可用排期

```
用户："预约明天的瑜伽课"
AI  ："📅 没有找到符合条件的排期
      2026-09-27 至 2026-10-04 暂无排期"
```

- `_parse_schedules` 返回空列表 → 不存 state → 直接返回提示。
- 不进入多轮选择。

## 分支 2：用户选择无效

```
用户："1"（在排期列表内）  → 正常预约
用户："99"（超出范围）     → "❌ 无法识别您的选择「99」... 请回复数字"
用户："abc"（非数字）      → "❌ 无法识别您的选择「abc」..."
```

- `_parse_user_selection` 返回 None → 重新展示选项，state 保留。

## 分支 3：预约写操作失败

- Service 层抛出业务异常（约满 / 重复预约 / 余额不足等）→ `_handle_business_error` 映射为友好提示，不回显原始异常。
- state 被清除，避免残留中间态。

## 不涉及

- 取消预约流程（confirming_cancel）不在本 Feature 改动范围。
- 前端 UI 不变（chat 契约不变）。
