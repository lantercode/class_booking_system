# 现有页面与原型映射（Existing Page Mapping）

> 勘察日期：2026-10-10
> 勘察方法：逐文件阅读真实前端源码（非猜测）。覆盖 `apps/admin-web`、`apps/student-web`、`apps/teacher-web`、`apps/miniapp` 四端的路由/页面清单文件（router/index.ts、pages.json）与会员卡相关页面组件源码，以及 `packages/api-client/src/membership.ts` 的 API 方法定义。
> 视觉规格细节（颜色值、布局尺寸、带文件:行号证据）见同目录 `ui-visual-spec.md`。

## 一、映射总表

| 业务功能 | 现有应用 | 现有页面 | 真实文件路径 | 路由/页面路径 | 当前能力 | 分类 | 原型补充内容 |
|---------|---------|---------|------------|-------------|---------|------|------------|
| 卡产品管理 | admin-web | 卡产品管理 | `apps/admin-web/src/views/card-types/index.vue` | `/card-types`（菜单"卡产品管理"，icon Collection） | 列表（产品名称/计费方式/包含次数/有效天数/价格/适用课程类型/状态），新增/编辑/上下架/删除/批量删除弹窗；仅支持次卡与期卡两种计费方式，无"无限卡"创建入口 | 1. 已有页面，只需要增加交互 | 若原型含无限卡/指定课程等新产品维度，需在新增/编辑弹窗中扩展选项与展示 |
| 会员卡管理列表 | admin-web | 会员卡管理 | `apps/admin-web/src/views/membership/index.vue` | `/membership`（菜单"会员卡管理"，icon CreditCard） | 列表（卡号/产品/计费方式/学员/手机号/总次数/已用/剩余/状态/有效期/冻结信息），搜索学员或手机号、状态多选筛选、分页；批量作废 | 1. 已有页面，只需要增加交互 | 原型若需筛选维度（按卡号精确查、按产品筛选）在此页补充 |
| 发卡 | admin-web | 会员卡管理-发放弹窗 | `apps/admin-web/src/views/membership/index.vue`（"发放会员卡"按钮 + 发放 dialog，模板 L207-L297） | 同上（页内弹窗） | 选学员（远程搜索）+ 选产品（自动带入次数/天数）+ 生效日期（含续卡最早日期限制 409 冲突处理）+ 备注；无限卡/期卡/次卡分支展示 | 1. 已有页面，只需要增加交互 | 原型演示完整发卡流程即可复用此弹窗结构 |
| 卡详情+流水 | admin-web | 会员卡管理-详情弹窗 | `apps/admin-web/src/views/membership/index.vue`（详情 dialog，模板 L299-L361） | 同上（页内弹窗） | 仅有 el-descriptions 只读信息（卡号/产品/学员/次数/状态/有效期/冻结信息/时间），**无任何使用流水/扣次记录展示** | 3. 页面存在，但缺少关键业务状态 | 原型需新增"使用流水"区块（后端已有流水数据源：小程序端 `membershipApi.transactions → GET /membership/transactions`；Web 端 api-client 未封装该方法） |
| 预约管理列表 | — | 无 | 无（admin 路由 `apps/admin-web/src/router/index.ts` 全量核对：dashboard/users/roles/teachers/students/courses/schedules/classrooms/tenant/membership/card-types，无 bookings/attendance 相关路由） | — | 管理后台完全没有任何预约管理页面 | 4. 当前没有对应页面，需要设计新增页面（**待新增**） | 新设计预约管理列表页（预约记录、状态筛选、取消/签到操作），风格对齐 admin-web 既有列表页 |
| 排期签到点名 | teacher-web | 学员列表（签到点名） | `apps/teacher-web/src/views/students/index.vue` | `/students/:scheduleId`（路由 title"学员列表"，页面 header 文案"学员列表"） | 排期信息卡（课程/时间/教室）+ 统计栏（已预约/已签到/未签到）+ 学员卡片列表（头像/姓名/手机号/状态 tag），对 status=confirmed 的预约提供"签到"按钮（bookingApi.checkIn） | 1. 已有页面，只需要增加交互 | 原型演示签到流程复用此页；如需"全选点名/批量签到"为新交互 |
| 我的会员卡列表 | miniapp | 我的会员卡 | `apps/miniapp/src/pages/student/membership/index.vue` | `pages/student/membership/index`（导航栏标题"我的会员卡"，pages.json L133-L137） | 有效/无效双 Tab；金渐变"使用中"卡、白色"已用完/未激活"卡、蓝灰"冻结中"卡、灰化"已过期/已作废"卡；状态徽标（使用中/已用完/未激活/冻结中/已过期/已作废）；复制卡号、立即激活、提前解冻按钮；空状态（前往办理+权益介绍） | 1. 已有页面，只需要增加交互 | 原型复用真实卡片视觉；如需"卡详情页"则为待新增（见下行） |
| 小程序卡详情+使用记录 | — | 无独立详情页 | 无（`pages/student/membership/index.vue` 为纯列表，卡片不可点击进入详情；无任何流水/使用记录 UI） | — | 无卡详情页、无使用记录展示；仅 API 层已有 `membershipApi.transactions`（`apps/miniapp/src/api/index.ts` L641，GET /membership/transactions） | 4. 当前没有对应页面，需要设计新增页面（**待新增**） | 新设计卡详情页：卡面大图+状态+余额+有效期+使用记录时间线，入口从"我的会员卡"卡片点击进入 |
| 课程排期选择 | miniapp | 排期（schedule） | `apps/miniapp/src/pages/student/schedule/index.vue` | `pages/student/schedule/index`（custom 导航） | 课程排期卡片列表（时间段/课程名/教室/教师/剩余容量），按钮文案"预约"/"已预约"/"不可预约"；已预约卡可取消；无卡时提示"您需要先办理会员卡才能预约课程"并引导办卡 | 1. 已有页面，只需要增加交互 | 原型演示"从排期进入预约"流程复用此页 |
| 预约确认选卡 | miniapp | 预约确认 | `apps/miniapp/src/pages/student/booking-confirm/index.vue` | `pages/student/booking-confirm/index`（custom 导航，标题"预约确认"） | 课程信息卡（名称/日期/时间/教室/教师/剩余名额）+"使用会员卡"选择区+注意事项卡（◆ 列表，含开课前 X 分钟不可取消）+底部弹窗选卡（radio 单选、不可用卡含原因徽标）+底部"取消/确认预约"操作栏 | 1. 已有页面，只需要增加交互 | 原型演示选卡预约流程复用此页；不可用卡原因徽标样式已齐备 |
| 预约结果 | — | 无独立结果页 | 无（预约成功仅为 `uni.showToast({ title: "预约成功" })` 后 1.5s 返回上一页，见 `booking-confirm/index.vue` handleConfirm L689-L693） | — | 无预约结果/成功页 | 4. 当前没有对应页面，需要设计新增页面（**待新增**） | 若原型需要"预约结果页"（成功态+预约详情+查看预约入口），需新设计；当前交互是 toast+返回 |
| 我的预约 | miniapp | 预约记录 | `apps/miniapp/src/pages/student/bookings/index.vue` | `pages/student/bookings/index`（custom 导航，标题"预约记录"） | 筛选 Tab（全部/待上课/上课中/已完成）+ 预约卡片（课程名/日期/教室/教师+状态徽标）+ 取消预约按钮（受开课前 X 分钟限制，超时显示"开课前X分钟内不可取消"） | 1. 已有页面，只需要增加交互 | 原型复用真实状态徽标与卡片样式 |
| 取消预约 | miniapp | 预约记录-取消 | `apps/miniapp/src/pages/student/bookings/index.vue`（handleCancel L280-L300） | 同上（页内交互） | uni.showModal 二次确认（"确认取消/确定要取消此预约吗？"）→ bookingApi.cancel → toast"取消成功" | 1. 已有页面，只需要增加交互 | 原型演示取消流程复用此交互；原型若需"取消后扣次回补提示"为新增状态展示 |
| 教师排期名单签到 | teacher-web | 学员列表 | `apps/teacher-web/src/views/students/index.vue` | `/students/:scheduleId` | 见"排期签到点名"行；教师 Web 端已有完整签到能力 | 1. 已有页面，只需要增加交互 | 同上 |
| 教师排期名单签到（小程序） | miniapp | 教师排期学员 | `apps/miniapp/src/pages/teacher/students/index.vue` | `pages/teacher/students/index`（custom 导航） | **存在签到能力**：统计栏（已签到/待签到）+ 学员列表，booking_status === 'booked' 时显示"签到"按钮（handleCheckIn）；预期"无独立签到页"成立——签到内嵌在学员名单页中，无独立页面 | 1. 已有页面，只需要增加交互 | 原型若演示教师端流程，按小程序内嵌签到形态呈现 |
| 核销记录查询 | — | 无 | 无（admin 无任何核销/流水页面；miniapp 有 API 无 UI：`membershipApi.transactions`；Web api-client `packages/api-client/src/membership.ts` 未封装 transactions 方法） | — | 全端无核销记录查询界面 | 4. 当前没有对应页面，需要设计新增页面（**待新增**） | 新设计核销/使用记录查询（admin 侧可挂在会员卡详情弹窗内作为流水 Tab；学员侧为卡详情页使用记录） |

## 二、分类说明

四类定义与归类结果：

### 1. 已有页面，只需要增加交互
页面真实存在且功能完整，原型主要是演示/复现现有交互流程，或补充小的操作入口：
- 卡产品管理（admin-web `/card-types`）
- 会员卡管理列表（admin-web `/membership`）
- 发卡（admin-web 会员卡管理页内"发放会员卡"弹窗）
- 排期签到点名（teacher-web `/students/:scheduleId`；miniapp `pages/teacher/students`）
- 我的会员卡列表（miniapp `pages/student/membership`）
- 课程排期选择（miniapp `pages/student/schedule`）
- 预约确认选卡（miniapp `pages/student/booking-confirm`）
- 我的预约（miniapp `pages/student/bookings`）
- 取消预约（miniapp 预约记录页内交互）

### 2. 已有页面，需要增加少量 UI 元素
（本次勘察中无严格属于此类的页面；admin 会员卡列表已具备状态筛选、批量作废等元素。若原型要求增加"按卡号筛选""按产品筛选"等，归入第 1 类的交互扩展。）

### 3. 页面存在，但缺少关键业务状态
- **卡详情+流水（admin-web）**：详情弹窗（`membership/index.vue` L299-L361）只有静态 descriptions 信息，没有使用流水/扣次/核销记录区块。流水数据后端已存在（小程序 API `GET /membership/transactions` 可用），仅管理端无 UI 呈现。

### 4. 当前没有对应页面，需要设计新增页面（待新增）
- **预约管理列表（admin-web）**：管理后台无任何预约管理页面（路由全量核对确认）。**待新增**。
- **小程序卡详情+使用记录**：会员卡列表页卡片不可点击、无详情页、无流水 UI。**待新增**。
- **预约结果页**：预约成功仅 toast 后返回，无结果页。**待新增**（若原型需要）。
- **核销记录查询**：全端无查询界面。**待新增**（admin 挂详情弹窗流水 Tab / 学员侧挂卡详情页使用记录）。

## 附：各端会员卡相关 API 方法清单（packages/api-client 与 miniapp）

`packages/api-client/src/membership.ts`：
- `cardTypeApi`：list / create / update / remove / listDeleted / restore / batchDeleteProducts（L146-L170）
- `membershipCardApi`：list / create / get / freeze / cancel / batchCancel / extend / unfreeze / studentUnfreeze / checkConflict / activate / adminActivate（L175-L226）
- 注意：Web 端 api-client **未封装** 流水（transactions）查询方法。

`apps/miniapp/src/api/index.ts`：
- `membershipApi`：getMyCards（L619） / getCard（L624） / activateCard（L627） / studentUnfreeze（L631） / transactions（L641）
- `bookingApi`：list / create / cancel / checkIn / complete（L509-L537）
