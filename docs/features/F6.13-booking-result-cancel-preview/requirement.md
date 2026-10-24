# F6.13 需求：预约结果页与取消回补预览（miniapp）

> 来源：F6.0 原型 P-M5《预约结果页》与 P-M7《取消确认弹窗（回补预览）》（`docs/features/F6.0-membership-card-prototype/interaction-spec.md` L145-151、`screen-inventory.md` 规划页清单）。
> 日期：2026-10-24。风险等级 **L2**（单域纯前端：仅 miniapp；**No DB change（已核对）**、不新增后端端点）。

## 1. 背景与现状差距

| 项 | 原型口径 | 真实端现状 |
|----|---------|-----------|
| 预约成功反馈 | 独立结果页 P-M5：成功=排期信息+「已预扣 1 次·剩余 N 次」（次卡）/「预约成功·首次上课后激活」（期卡）；失败=错误分类与建议动作 | 仅 `booking-confirm/index.vue:458` `uni.showToast('预约成功')` 轻提示，无扣次反馈、无失败分类页 |
| 取消确认 | 弹窗 P-M7：展示回补预览（将回补 N 次）后确认 | 取消入口直接调用，无回补预览确认弹窗 |

## 2. 已冻结契约

| # | 端点 | 状态 | 说明 |
|---|------|------|------|
| K1 | `POST /api/v1/bookings/` | ✅ 已有 | body: `schedule_id` + `membership_card_id`；响应 `Booking` 含 `card_type`/`remaining_credits`/`card_no`；失败错误码区分 400（余额不足/卡不可用）/409（名额满/时间重叠） |
| K2 | `POST /api/v1/bookings/cancel` | ✅ 已有 | body: `schedule_id` + `reason`；取消成功回补次数（RESTORE 流水），回补次数可由所选卡 `card_type`（count=1 次/unlimited、period=0 次）推导 |

> 无后端改动；回补预览为**纯展示推导**，最终以取消后实际余额为准（后端权威）。

## 3. Scope

### 3.1 In Scope

- `apps/miniapp/src/pages/student/booking-result/index.vue`（新建，注册 `pages.json`）：
  - 成功态：排期摘要（课程/时间/教师/教室）+ 扣次反馈——次卡「已预扣 1 次·剩余 N 次」（取响应 `remaining_credits`）；期卡「预约成功·首次上课后激活」；不限卡「预约成功」。
  - 失败态：按 HTTP 400/409 与后端 `msg` 分类展示建议动作（换卡重试 / 选其他排期 / 联系机构），提供「返回重选」「查看我的预约」出口。
  - 出口：查看预约（→ 我的预约）/ 返回首页。
- `apps/miniapp/src/pages/student/booking-confirm/index.vue`：提交成功后 `redirectTo` 结果页（携带响应数据）；失败跳转结果页失败态（或 toast+停留，二选一以实现评估为准，需在交付说明中记录选择）。
- `apps/miniapp/src/pages/student/bookings/index.vue`：取消操作改为 P-M7 确认弹窗——弹窗内展示回补预览（次卡「取消后将回补 1 次」/期卡「期卡不涉及次数回补」/无限卡「不涉及次数回补」）+ 取消原因输入（保持现有接口参数），确认后调 `cancel`。

### 3.2 Out of Scope

- 后端任何改动；改期 UI（F6.5 仅后端）；退款；AI 侧改动。
- 预约列表页其它改造（F6.7 警示条已交付，不动）。

## 4. 验收要点

1. 成功/余额不足/名额满三分支齐全，文案与后端 msg 一致，无内部信息回显。
2. 次卡扣次反馈与实际余额一致；期卡文案正确。
3. 取消弹窗回补预览与卡类型匹配；写操作有二次确认。
4. `vue-tsc` + `build:mp-weixin` 通过；新页四态齐全。

## 5. Required Agents

frontend-engineer（主，L2 自查替代 architect Review）。
