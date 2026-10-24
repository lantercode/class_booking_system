# F6.0 原型页面清单（Screen Inventory）

> 日期：2026-10-09
> 页面分三类：**现有**（代码已存在，原型按现状复刻+标注升级点）、**规划**（本次原型新增设计）、**占位**（依赖未确认决策/未实现后端能力）
> 每页的完整规格（字段/操作/成功失败/状态变化/API/验收）见 interaction-spec.md 对应编号

## 一、现有页面盘点（原型基线）

### admin-web（管理后台，Vue3+Element Plus）

| 编号 | 页面 | 路由 | 会员卡相关度 | 证据 |
|------|------|------|-------------|------|
| A1 | 控制台 | /dashboard | 低 | router/index.ts:24 |
| A2 | 用户/角色/教师/学员管理 | /users /roles /teachers /students | 低 | :30-52 |
| A3 | 课程/排期/教室管理 | /courses /schedules /classrooms | 中（排期是预约对象） | :54-70 |
| A4 | 机构设置 | /tenant | 低 | :72-76 |
| A5 | **卡产品管理** | /card-types | 高 | :84-88；views/card-types/index.vue:364-459 |
| A6 | **会员卡管理** | /membership | 高 | :78-82；views/membership/index.vue（发放/激活/冻结/解冻/作废/批量作废） |
| — | ❌ 预约管理 | 无此路由 | **核心缺口** | router/index.ts 全文无 bookings |

### miniapp（学员/教师小程序，uni-app）

| 编号 | 页面 | 路径 | 会员卡相关度 | 证据 |
|------|------|------|-------------|------|
| M-idx | 登录/绑定 | pages/index、pages/bind/manual | 低 | pages.json:9-23 |
| M1 | 教师端：课程/排期/学员/资料 | pages/teacher/* | 低（无签到页） | :25-77 |
| M2 | 学员课程列表/详情/排期 | pages/student/courses/*、schedule | 高入口 | :79-105 |
| M3 | **预约确认（选卡）** | pages/student/booking-confirm | 高 | :139-144；选卡逻辑 booking-confirm/index.vue:642-672 |
| M4 | 学员我的预约 | pages/student/bookings | 高 | :107-112 |
| M5 | **我的会员卡** | pages/student/membership | 高 | :133-137；membership/index.vue |
| M6 | 个人中心/视频/通知 | pages/student/profile、videos、notification | 低 | :114-158 |
| — | ❌ 卡详情页 | 无 | API 已备无页面 | api/index.ts:623 getCardDetail 零页面消费 |
| — | ❌ 使用记录页 | 无 | API 已备无页面 | api/index.ts:635 getTransactions 零页面消费 |

### student-web（学员 Web）

| 页面 | 会员卡相关度 | 结论 |
|------|-------------|------|
| /courses /courses/:id /courses/:id/schedule /my-bookings /profile | **零** | 全目录 grep `membership` 零命中；预约不传 membership_card_id。本次原型**不覆盖 student-web**（以小程序为学员主端），仅登记差距 |

### teacher-web（教师 Web）

| 编号 | 页面 | 会员卡相关度 | 证据 |
|------|------|-------------|------|
| T1 | 我的排期/课程 | 中 | views/courses、schedule |
| T2 | **排期学员名单+签到** | 高（考勤入口） | views/students/index.vue:139 list、:171 checkIn（真实 API） |
| — | ❌ "完成"动作 | 后端端点存在，页面未接 | bookingApi.complete 已在 api-client |

### mock 残留登记（原型演示不得依赖）

`admin-web/src/mock/index.ts`、`student-web/src/mock/{courses,bookings,schedules}.ts`、`teacher-web/src/mock/{courses,students,schedules}.ts`；已核实 teacher-web 名单页与 admin membership 页走真实 API。

## 二、原型页面规划（本次 Figma 交付范围）

| 原型编号 | 页面 | 端/角色 | 类型 | 对应流程 | 决策占位 |
|---------|------|--------|------|---------|---------|
| P-A1 | 卡产品管理（升级：适用课程/每周上限编辑体验） | 管理端/管理员 | 现有升级 | A | — |
| P-A2 | 会员卡管理列表（现有+受影响预约警示） | 管理端/管理员 | 现有升级 | A/E/F | D3 |
| P-A3 | 发卡弹窗（现有+生效日期/重复卡策略） | 管理端/管理员 | 现有升级 | A | D4 |
| P-A4 | **卡详情+流水**（新） | 管理端/管理员 | 规划 | G | — |
| P-A5 | **预约管理列表**（新） | 管理端/管理员 | 规划 | C/D/E/F | D3/D5 |
| P-A6 | **排期签到点名**（新，管理端代签到） | 管理端/管理员 | 规划 | D | D1/D5 |
| P-M1 | 我的会员卡列表（现有：状态徽标/余额/有效期/操作） | 小程序/学员 | 现有升级 | A/F | D2 |
| P-M2 | **卡详情**（新：信息+使用记录） | 小程序/学员 | 规划 | A/G | D2/D4 |
| P-M3 | 课程排期选择（现有） | 小程序/学员 | 现有 | A | — |
| P-M4 | 预约确认选卡（现有：默认推荐/切换/余额预览） | 小程序/学员 | 现有升级 | A/B | D6 |
| P-M5 | 预约结果页（成功含扣次反馈/失败原因分类） | 小程序/学员 | 规划 | A/B | D1 |
| P-M6 | 我的预约（现有+计划卡状态警示条） | 小程序/学员 | 现有升级 | C/E | D3 |
| P-M7 | 取消确认弹窗（回补预览） | 小程序/学员 | 规划 | C | D7 |
| P-T1 | 教师排期名单签到（现有升级：完成按钮/重复签到反馈） | 教师端/教师 | 现有升级 | D | D1/D5 |

> 覆盖检查：流程 A→P-A1/A2/A3/P-M1/P-M3/P-M4/P-M5；B→P-M4；C→P-M6/P-M7/P-A5；D→P-T1/P-A6；E→P-M6/P-A2/P-A5；F→P-M1/P-M2/P-A2；G→P-M2/P-A4。**A-G 全覆盖**。

> 补充（2026-10-19）：P-M3/P-M4 增「**跨排期时间段重叠冲突**」演示态——目标排期 S6（2026-10-10 19:30-20:30）与学员已有进行中预约 B1 所在排期 S1（2026-10-10 19:00-20:30）时间重叠，在确认预约阶段被拦截（不生成新预约）；该状态与既有「会员卡有效期重叠」拦截相互独立。触发/行为/文案见 interaction-spec.md P-M3/P-M4，验收见 prototype-acceptance.md AC11，真实后端缺口见 open-decisions.md（D10）。
