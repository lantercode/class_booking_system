# F6.10 需求：管理端预约管理与卡详情/流水 UI

> 来源：`docs/delivery/feature-backlog.md`「Feature 6.10」（L609-625）。
> 日期：2026-10-24。风险等级 **L3**（单域前端特性，涉及 6 文件、不改核心状态机；**No DB change（已核对）**、不新增后端端点）。

## 1. Stage 1 READY 结论

| 项 | 结论 |
|----|------|
| Selected Feature | F6.10 管理端预约管理与卡详情/流水 UI |
| Why | admin-web 无预约管理入口（`router/index.ts:74-84` 仅 tenant/membership/card-types 等）；会员卡详情弹窗无流水（`views/membership/index.vue` 全文无 `getTransactions` 调用）；教师端学员列表仅签到无「完成」按钮（`teacher-web/src/views/students/index.vue:169-171`） |
| Dependencies | F6.3/F6.4/F6.5/F6.7 后端契约 ✅ 已交付；`@dance-saas/api-client` 已有 `getTransactions`（`membership.ts:255-263`）、`checkIn`/`complete`（`bookings.ts:60-66`） |
| Existing Capabilities | 见 §1.2 |
| Missing Capabilities | 见 §1.3 |
| Risks | 见 implementation-plan.md §风险 |
| Required Agents | frontend-engineer（主）、project-architect（契约复核/Review） |
| Definition of Ready | **READY**：后端端点全部存在并已核对；不涉及 DB/后端改动 |

### 1.1 已冻结契约（后端端点核对结论）

| # | 端点 | 后端存在 | 权限 | 说明 |
|---|------|----------|------|------|
| K1 | `GET /api/v1/bookings` | ✅ | 按角色分流（admin 看全量） | 支持 `schedule_id` / `status`（逗号分隔）/ `display_status` / `page` / `page_size` 筛选 |
| K2 | `POST /api/v1/bookings/{id}/check-in` | ✅ | `booking:manage` | 状态 1（已预约）→ 3（已签到） |
| K3 | `POST /api/v1/bookings/{id}/complete` | ✅ | `booking:manage` | 状态 3（已签到）→ 4（已完成） |
| K4 | `GET /api/v1/membership/transactions?card_id=` | ✅ | 租户隔离 | 卡流水分页查询 |
| K5 | `GET /api/v1/membership/cards/{id}/affected-bookings` | ✅（F6.7） | — | 受影响预约，**本期不重复集成**（admin-web 冻结/作废弹窗已在 F6.7 接入） |

> 契约核对方式：逐方法核对 `booking/router.py`、`membership/router.py` 真实路由；`BookingResponse`（`booking/schemas.py:39-69`）已含 `course_name`/`start_at`/`end_at`/`classroom_name`/`teacher_name`/`display_status` 关联字段。

### 1.2 可复用能力（真实代码证据）

| 能力 | 位置 | 说明 |
|------|------|------|
| 预约列表接口 | `packages/api-client/src/bookings.ts:44-46` `bookingApi.list` | 已存在，`BookingListParams` 缺 `display_status`、`status` 仅 `number`（需扩展为 `string \| number` 以支持多选逗号拼接） |
| 签到/完成接口 | `bookings.ts:60-66` `checkIn`/`complete` | 已存在，直接复用 |
| 卡流水接口 | `membership.ts:255-263` `membershipCardApi.getTransactions` | 已存在，参数 `{card_id, page, page_size}` |
| 流水类型定义 | `membership.ts:124-137` `MembershipCardTransaction` | 含 `operation_type`/`change_amount`/`balance_after`/`created_at` 等 |
| 流水操作类型枚举 | `apps/api/src/app/modules/membership/models.py:58-67` `TransactionType` | `issue`/`consume`/`restore`/`recharge`/`refund`/`adjust`/`expire` |
| 四态列表范式 | `admin-web/src/views/membership/index.vue`（loading/empty/error/data） | 复用其 `el-skeleton` + `el-empty` + `el-result` + `el-table` 四态模式 |
| 影响面四态范式 | `membership/index.vue:743-773` `resetAffectedState`/`loadAffectedBookings` | 含请求序号防竞态，流水加载同构复用 |
| 教师端签到逻辑 | `teacher-web/src/views/students/index.vue:169-177` `checkIn` | 状态映射 `b.status===3 → 'attended'`，完成按钮同构 |
| 菜单/路由范式 | `admin-web/src/router/index.ts`、`layout/AdminLayout.vue:144-156` | 新增路由与菜单项的既有结构 |

### 1.3 缺失能力

1. admin-web 路由无 `/bookings`，菜单无「预约管理」入口。
2. `packages/api-client/src/bookings.ts` 的 `Booking` 接口缺 `course_name`/`start_at`/`end_at`/`classroom_name`/`teacher_name`/`display_status`（后端 `BookingResponse` 已有，前端类型未对齐）；`BookingListParams.status` 仅 `number`，不支持多选逗号拼接，且缺 `display_status`。
3. admin-web 无预约管理页面（`views/bookings/index.vue` 不存在）。
4. 会员卡详情弹窗（`membership/index.vue:304-366`）仅展示卡基本信息，无流水区块。
5. 教师端学员列表（`teacher-web/src/views/students/index.vue`）已签到学员无「完成」按钮。

## 2. Scope

### 2.1 In Scope

- `packages/api-client/src/bookings.ts`：扩展 `Booking` 接口字段；扩展 `BookingListParams`（`status` 支持 `string | number`，新增 `display_status`）。
- `apps/admin-web/src/router/index.ts`：新增 `/bookings` 路由（meta title「预约管理」，icon `Calendar`）。
- `apps/admin-web/src/layout/AdminLayout.vue`：`menuItems` 新增「预约管理」项（置于「排期管理」之后）。
- `apps/admin-web/src/views/bookings/index.vue`（新建）：预约管理页——筛选区（排期 ID 输入、状态多选）、`el-table` 列表（学员昵称/手机号、课程名、上课时间、状态 tag、操作按钮）、四态（loading skeleton / empty / error / data）、分页。
- `apps/admin-web/src/views/membership/index.vue`：详情弹窗（`detailDialogVisible`，约 304-366 行）底部新增流水区块——打开详情时按 `card_id` 调 `getTransactions`，`el-table` 展示 `operation_type`/`change_amount`/`created_at`，分页。
- `apps/teacher-web/src/views/students/index.vue`：`student.status === 'attended'`（已签到，对应 `status=3`）时在签到按钮旁新增「完成」按钮，调 `bookingApi.complete(id)`。

### 2.2 Out of Scope

- 退款（F6.9）、改期 UI（F6.5 仅后端，UI 另评估）。
- 卡产品编辑重构、学员端（F6.11）。
- 后端任何改动（端点/Service/Repository/DB 均不动）。
- 受影响预约（F6.7 已在 admin-web 冻结/作废弹窗接入，本期不重复）。
- 预约状态机改动、批量操作、导出。

## 3. 业务规则

| # | 规则 |
|---|------|
| R-1 | 预约状态枚举（`BookingResponse.status`）：1=已预约 / 2=已取消 / 3=已签到 / 4=已完成 / 5=未到场。admin 列表页状态多选筛选以此为准，多选时以逗号拼接传入 `status` query（后端支持逗号分隔）。 |
| R-2 | 显示状态（`display_status`）：1=待上课 / 2=已取消 / 3=上课中 / 4=已完成。列表状态 tag 优先按 `display_status` 渲染（语义更贴近学员视角），但操作按钮显隐按 `status` 判断。 |
| R-3 | 操作按钮显隐：`status === 1`（已预约）显示「签到」按钮；`status === 3`（已签到）显示「完成」按钮；其余状态无操作按钮。 |
| R-4 | 签到/完成写操作调后端既有 `POST /bookings/{id}/check-in`、`POST /bookings/{id}/complete`，需 `booking:manage` 权限；按钮带 loading，成功后局部刷新该行状态并 toast，失败展示后端 `msg`。 |
| R-5 | 卡流水查询：详情弹窗打开时按当前 `detailCard.id` 调 `GET /membership/transactions?card_id={id}&page=1&page_size=10`；流水区块独立四态，查询失败不阻断详情展示。 |
| R-6 | 流水字段展示：`operation_type` 映射为中文（issue=开卡 / consume=扣减 / restore=恢复 / recharge=充值 / refund=退款 / adjust=调整 / expire=过期清零）；`change_amount` 正数绿色、负数红色；`created_at` 本地格式化。 |
| R-7 | 教师端「完成」按钮：仅在 `student.status === 'attended'`（后端 `status=3` 已签到）时显示；成功后 `student.status = 'completed'`，按钮消失。 |
| R-8 | 前端只通过 `@dance-saas/api-client` 调用后端，禁止在前端复制业务规则作为最终校验；所有写操作成功与否以后端响应为准。 |
| R-9 | 四态完整性：列表与流水区块均须覆盖 loading（skeleton）/ empty（el-empty）/ error（el-result + 重试）/ data 四态，不得空白闪烁。 |
| R-10 | 分页：预约列表与卡流水均支持分页，页码变化时重新请求并保留筛选条件。 |

## 4. 响应契约（已存在，仅列前端消费字段）

### 4.1 `GET /api/v1/bookings`

请求参数（`BookingListParams`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `schedule_id` | number? | 排期 ID 精确筛选 |
| `status` | string \| number? | 状态；多选逗号拼接（如 `"1,3"`） |
| `display_status` | number? | 显示状态（1-4） |
| `page` | number? | 页码，默认 1 |
| `page_size` | number? | 每页，默认 20 |

响应 `BookingResponse` 关键字段（`booking/schemas.py:39-69`）：

| 字段 | 说明 |
|------|------|
| `id` | 预约 ID |
| `status` | 1已预约/2已取消/3已签到/4已完成/5未到场 |
| `display_status` | 1待上课/2已取消/3上课中/4已完成 |
| `student_nickname` / `student_phone` | 学员昵称/手机号（关联） |
| `course_name` / `start_at` / `end_at` / `classroom_name` / `teacher_name` | 课程/时间/教室/教师（关联） |
| `booked_at` / `checked_in_at` | 预约/签到时间 |

### 4.2 `GET /api/v1/membership/transactions?card_id=`

响应 `MembershipCardTransaction`（`membership.ts:124-137`）关键字段：

| 字段 | 说明 |
|------|------|
| `operation_type` | issue/consume/restore/recharge/refund/adjust/expire |
| `change_amount` | 变动课时数（正为增加，负为扣减） |
| `balance_after` | 变动后余额 |
| `remark` | 备注 |
| `created_at` | 流水时间 |

### 4.3 四端影响面确认

| 端 | 影响 |
|----|------|
| admin-web | **改**：新增预约管理页、卡详情流水区块、路由/菜单 |
| teacher-web | **改**：学员列表已签到学员加「完成」按钮 |
| student-web | 不涉及（Out of Scope，显式确认） |
| miniapp | 不涉及（显式确认） |

## 5. 用户故事

| # | 角色 | 故事 |
|---|------|------|
| US-1 | 机构管理员 | 我能在管理端查看全租户预约列表，按排期和状态筛选，快速定位待上课学员。 |
| US-2 | 机构管理员 | 我能在预约列表直接为已预约学员代签到、为已签到学员标记完成，无需跳转排期页。 |
| US-3 | 机构管理员 | 我能在会员卡详情弹窗查看该卡的课时流水，核对扣减/恢复记录。 |
| US-4 | 教师 | 我能在教师端学员列表为已签到的学员标记完成课程。 |
