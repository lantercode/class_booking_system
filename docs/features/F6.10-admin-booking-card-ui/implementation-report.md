# F6.10 实施报告

- Feature：F6.10 管理端预约管理与卡详情/流水 UI
- 日期：2026-10-24
- 状态：开发完成，待人工验收

## 实施范围

L3 前端任务为主；为对齐原型「计划卡」列与「代取消」操作，补充后端只读字段与 admin 取消端点。无 DB 迁移、未重新生成 api-types。

## 改动清单

| # | 文件 | 任务 | 概要 |
|---|------|------|------|
| 1 | `packages/api-client/src/bookings.ts` | T6.10.1 | `Booking` 加 `course_name/start_at/end_at/classroom_name/teacher_name/display_status/card_no/card_status/card_type/remaining_credits`；`BookingListParams.status` 放宽为 `string \| number`，加 `display_status`；新增 `adminCancel` |
| 2 | `apps/admin-web/src/router/index.ts` | T6.10.2 | 新增 `/bookings` 路由 |
| 3 | `apps/admin-web/src/layout/AdminLayout.vue` | T6.10.2 | menuItems 加「预约管理」（排期管理之后） |
| 4 | `apps/admin-web/src/views/bookings/index.vue` | T6.10.2 | 预约管理页对齐原型：学员/课程排期/状态/计划卡/来源/取消原因/操作；代取消(ElMessageBox 输入原因)/签到/完成按钮；卡失效行高亮 |
| 5 | `apps/admin-web/src/views/membership/index.vue` | T6.10.3 | 详情弹窗加「课时流水」区块（四态+表格+分页+防竞态） |
| 6 | `apps/teacher-web/src/views/students/index.vue` | T6.10.4 | 已签到状态加「完成」按钮 |
| 7 | `apps/api/src/app/modules/booking/schemas.py` | 后端 | `BookingResponse` 加 `card_no/card_status/card_type/remaining_credits` |
| 8 | `apps/api/src/app/modules/booking/service.py` | 后端 | `list_bookings` 批量查卡填充；`_to_response` 加 card_info 参数；新增 `admin_cancel_booking`（复用 `_do_cancel_booking`） |
| 9 | `apps/api/src/app/modules/booking/router.py` | 后端 | 新增 `POST /bookings/{id}/admin-cancel`（`booking:manage`） |

## 关键实现决策

- **状态口径**：筛选用 `status`（1-5 多选逗号拼接）；tag 渲染优先 `display_status`（1-4），`status===5` 单独 danger；按钮显隐按 `status===1` 代取消+签到、`status===3` 完成。
- **计划卡列**：`card_no` + 卡状态 tag（使用中绿/已用尽橙[次卡剩余0]/已过期灰/已冻结蓝/已作废红/未激活灰）；卡失效（已作废/已过期）行整行浅橙高亮。
- **代取消**：ElMessageBox.prompt 收集原因，调 `adminCancel`，复用 `_do_cancel_booking`（行锁+幂等回补+名额释放）。
- **局部更新**：签到/完成/取消成功后只更新当前行 status/display_status，不全表重载。
- **防竞态**：卡流水加载用 `transactionReqSeq` 序号模式（复用 F6.7 loadAffectedBookings 模式）。
- **改期**：按钮置灰占位（F6.5 仅后端，UI 待评估）。

## 迭代调整（2026-10-24 第二轮，原型对齐后）

1. **预约管理页加回「序号」列**（`type="index"`）。
2. **会员卡号生成规则**：由 `yyyyMMdd+9位随机数` 改为 `MC+yyyyMMdd+9位随机数`；`membership_cards.card_no` 列长度 17→19，新增迁移 `b8c9d0e1f2a3`。
3. **筛选改造**：「排期 ID」输入框替换为关键词搜索框「搜索学员/课程/排期」（学员昵称/手机号、课程名、排期ID 模糊匹配）；后端 `list_bookings` 新增 `keyword` 参数（JOIN users/course_schedules/courses）。
4. **筛选栏精简**：移除「查询/重置」按钮，状态下拉宽度 260→160px，搜索回车/清空即触发，与会员卡/排期页风格一致。

## 依赖

- 后端：新增 1 个端点 + 4 个只读响应字段 + keyword 检索 + card_no 迁移；无其他 DB 结构变更。
- F6.7 受影响预约：已集成，复用。
