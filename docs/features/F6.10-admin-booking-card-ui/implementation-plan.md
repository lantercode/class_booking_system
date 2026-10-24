# F6.10 实施计划：管理端预约管理与卡详情/流水 UI

> 日期：2026-10-24。依据 requirement.md（K1–K5 核对）、acceptance.md（A/D/E/F 分层）。
> Agent 分工：frontend-engineer（T6.10.1–T6.10.5）、project-architect（契约复核/Review）。**No DB change（已核对）**，无后端改动。

## 1. 架构决策

### 1.1 不改后端，仅消费既有契约

本 Feature 全部为前端 UI 补齐，后端端点（K1–K5）均已存在并核对：

- `GET /api/v1/bookings`（`booking/router.py`）——Service 层按角色分流，admin 看全量。
- `POST /api/v1/bookings/{id}/check-in`、`POST /api/v1/bookings/{id}/complete`（`booking:manage`）。
- `GET /api/v1/membership/transactions?card_id=`（`membership/router.py:486-507`）。
- `GET /api/v1/membership/cards/{id}/affected-bookings`（F6.7 已集成，本期不重复）。

前端类型以 `BookingResponse`（`booking/schemas.py:39-69`）为准，`Booking` 接口需补齐关联字段。

### 1.2 状态口径

- **筛选**用 `status`（1-5）：1待上课/2已取消/3已签到/4已完成/5未到场（label 采用学员视角，1 标「待上课」）。多选以逗号拼接，故 `BookingListParams.status` 类型由 `number` 放宽为 `string | number`。
- **展示 tag** 用 `display_status`（1-4）：1待上课/2已取消/3上课中/4已完成；`status=5`（未到场）不在 display_status 枚举内，单独渲染 danger tag。
- **操作按钮显隐** 用 `status`：`status===1` 显示签到；`status===3` 显示完成。

### 1.3 调用链

```
admin-web /bookings 页面
  → bookingApi.list / checkIn / complete（packages/api-client/src/bookings.ts）
  → HTTP /api/v1/bookings...（后端既有，不动）

admin-web 会员卡详情弹窗
  → membershipCardApi.getTransactions（packages/api-client/src/membership.ts:255-263）
  → HTTP /api/v1/membership/transactions（后端既有，不动）

teacher-web 学员列表
  → bookingApi.complete（packages/api-client/src/bookings.ts:64-66）
  → HTTP /api/v1/bookings/{id}/complete（后端既有，不动）
```

## 2. 文件白名单（允许改动）

| # | 文件 | 改动 |
|---|------|------|
| 1 | `packages/api-client/src/bookings.ts` | `Booking` 接口加 `course_name`/`start_at`/`end_at`/`classroom_name`/`teacher_name`/`display_status`；`BookingListParams.status` 改为 `string \| number`，加 `display_status?` |
| 2 | `apps/admin-web/src/router/index.ts` | 新增 `/bookings` 路由（meta title「预约管理」，icon `Calendar`），置于 `schedules` 之后 |
| 3 | `apps/admin-web/src/layout/AdminLayout.vue` | `menuItems` 新增 `{ path: '/bookings', title: '预约管理', icon: Calendar }`，置于「排期管理」之后（`:152` 之后） |
| 4 | `apps/admin-web/src/views/bookings/index.vue` | **新建**预约管理页（筛选区 + 表格 + 四态 + 分页 + 签到/完成） |
| 5 | `apps/admin-web/src/views/membership/index.vue` | 详情弹窗（`:304-366`）`</el-descriptions>` 后加流水区块；`openDetailDialog` 中触发流水加载；新增流水状态 + 加载函数（仿 `loadAffectedBookings`） |
| 6 | `apps/teacher-web/src/views/students/index.vue` | `:74-82` 签到按钮后加「完成」按钮（`v-if="status==='attended'"`）；新增 `complete` 函数 |

### 明确禁止改动

- 后端任何文件（`apps/api/**`）——端点/Service/Repository/DB 均不动。
- `packages/api-types` 生成产物（不重新生成，本 Feature 不改后端 OpenAPI）。
- `packages/api-client/src/membership.ts`（`getTransactions` 已存在，不改动）。
- student-web / miniapp 全部文件（Out of Scope）。
- 卡状态机、预约状态机、退款（F6.9）、改期 UI。

## 3. 任务拆分（T6.10.1 ~ T6.10.5）

| # | 任务 | Agent | 依赖 | 验收映射 |
|---|------|-------|------|----------|
| T6.10.1 | api-client 类型扩展：`Booking` 补关联字段，`BookingListParams.status` 放宽 + `display_status` | frontend | — | A-1、A-6 |
| T6.10.2 | admin-web 路由 + 菜单 + 预约管理页（筛选/列表/四态/分页/签到/完成） | frontend | T6.10.1 | A-2、A-3、D-1.*、E-1、E-2、F-1、F-2 |
| T6.10.3 | admin-web 会员卡详情弹窗流水区块（加载/四态/表格/分页） | frontend | T6.10.1（流水接口已存在，不依赖 T6.10.2） | A-2、A-3、D-2.*、E-3、F-3 |
| T6.10.4 | teacher-web 学员列表「完成」按钮 + 完成函数 | frontend | T6.10.1 | A-4、A-5、D-3.*、F-4 |
| T6.10.5 | 全量构建验证 + 人工验收 | frontend + architect | T6.10.2、T6.10.3、T6.10.4 | A-1..A-7、F-5、F-6 |

### 依赖顺序

```
T6.10.1（api-client 类型）
  ├─→ T6.10.2（admin 预约页）─┐
  ├─→ T6.10.3（admin 卡流水）─┤
  └─→ T6.10.4（teacher 完成） ─┴─→ T6.10.5（构建 + 人工验收）
```

- T6.10.2、T6.10.3、T6.10.4 之间**无相互依赖**，可并行（但注意 T6.10.2 与 T6.10.3 都改 admin-web，须串行合并避免冲突；T6.10.4 改 teacher-web，可真正并行）。
- T6.10.2 与 T6.10.3 同属 admin-web，建议同一前端 Agent 串行处理，避免同仓库并发冲突。

## 4. 关键实现要点

### 4.1 T6.10.1：api-client bookings.ts

```ts
// Booking 接口新增（对齐 booking/schemas.py:63-67, 48）
course_name?: string | null
start_at?: string | null
end_at?: string | null
classroom_name?: string | null
teacher_name?: string | null
display_status?: number  // 1待上课/2已取消/3上课中/4已完成

// BookingListParams
status?: string | number   // 多选时传逗号拼接字符串
display_status?: number
```

### 4.2 T6.10.2：admin-web 预约管理页

- 状态选项常量：`[{label:'待上课',value:1},{label:'已取消',value:2},{label:'已签到',value:3},{label:'已完成',value:4},{label:'未到场',value:5}]`。
- `status` 多选 `el-select multiple`，提交时 `statusFilter.value.join(',')`；空数组不传该参数。
- 状态 tag 函数：优先 `display_status` 映射，`status===5` 单独 danger。
- 签到/完成按钮：行内 `loading` 状态（用 `Map<id, boolean>` 或行对象字段），成功后更新该行 `status` 并刷新按钮显隐（无需全列表重载，局部更新即可）。
- 四态：`loading`（`v-loading` 或 skeleton）/ `total===0`（el-empty）/ `error`（el-result + 重试）/ data（el-table）。

### 4.3 T6.10.3：卡详情流水

- 复用 `loadAffectedBookings`（`index.vue:750-767`）的请求序号防竞态模式，新增 `transactionLoading`/`transactionError`/`transactionData`/`transactionReqSeq`。
- `openDetailDialog`（`:903`）中调用 `loadTransactions(detailCard.id)`。
- 弹窗内 `</el-descriptions>`（`:365`）之后、`</el-dialog>`（`:366`）之前插入流水区块：标题「课时流水」+ 四态 + el-table + el-pagination。
- `operation_type` 中文映射常量；`change_amount` 颜色：`>0` 绿、`<0` 红、`===0` 灰。
- 关闭弹窗（`detailDialogVisible` 变 false）时清空流水状态。

### 4.4 T6.10.4：teacher-web 完成按钮

- 在签到按钮（`:74-82`）后新增：
```vue
<el-button
  v-if="student.status === 'attended'"
  size="small"
  type="success"
  text
  @click="complete(student)"
>
  完成
</el-button>
```
- 新增 `complete` 函数（仿 `checkIn`，`:169-177`）：调 `bookingApi.complete(student.id)`，成功 `student.status = 'completed'`。

## 5. 测试与验证

### 5.1 构建/类型检查

| 命令 | 预期 |
|------|------|
| `pnpm --filter @dance-saas/api-client build` | 通过 |
| `pnpm --filter admin-web type-check`（或 `vue-tsc -b`） | 通过 |
| `pnpm --filter admin-web build` | 通过 |
| `pnpm --filter teacher-web type-check` | 通过 |
| `pnpm --filter teacher-web build` | 通过 |

### 5.2 人工验收

按 acceptance.md §F 逐项：预约筛选/签到/完成全流程、卡详情流水、教师端完成按钮、错误提示、四态完整性。

### 5.3 回归

- 本 Feature 不改后端、不改 api-client 的 membership 方法，回归面仅限：
  - admin-web 会员卡详情弹窗原有卡信息展示不被流水区块破坏。
  - teacher-web 学员列表原有签到功能不受影响。

## 6. 风险

| # | 风险 | 等级 | 缓解 |
|---|------|------|------|
| R-1 | admin-web 预约页与卡流水均改 `membership/index.vue`/admin-web，若并行开发可能冲突 | 中 | T6.10.2/T6.10.3 同一 Agent 串行处理；T6.10.4 改 teacher-web 可并行 |
| R-2 | `BookingListParams.status` 类型由 `number` 放宽为 `string \| number` 可能影响既有调用方 | 低 | 全库 grep `bookingApi.list` 调用点确认无破坏；teacher-web 既有传 `{schedule_id, page_size}` 不受影响 |
| R-3 | `display_status` 在部分历史预约可能为 null/未返回 | 低 | tag 渲染做兜底：`display_status` 为空时回退用 `status` 映射 |
| R-4 | 流水 `operation_type` 出现未枚举值 | 低 | 映射函数兜底返回原值（unknown 显示原始字符串） |
| R-5 | 卡流水与卡详情共用弹窗，加载竞态（快速开关） | 低 | 复用请求序号模式（`loadAffectedBookings` 先例），关闭弹窗清空状态 |

## 7. UNKNOWN

| # | 问题 | 默认处理 |
|---|------|----------|
| U-1 | 预约页状态筛选用 `status` 还是 `display_status` | 用 `status`（1-5，含未到场）；`display_status` 仅作 tag 渲染，筛选参数保留字段但本期 UI 不暴露 |
| U-2 | 流水 page_size 默认值 | 10（与 admin-web 列表页一致） |
| U-3 | 学员手机号是否脱敏 | admin 端不脱敏（既有会员卡页已明文展示手机号） |
| U-4 | 签到/完成成功后是否全列表刷新 | 局部更新行状态即可（性能更优）；如产品要求实时一致性可改全量刷新 |

## 8. Handoff 摘要

- **→ frontend-engineer**：实施 T6.10.1–T6.10.5。关键约束：仅改白名单 6 文件；不改后端、不重新生成 api-types；`Booking` 字段对齐 `booking/schemas.py`；四态必须齐全；操作按钮显隐按 `status` 判断；流水加载复用请求序号防竞态。
- **→ project-architect（Review）**：核对契约对齐（A-6）、分层合规（A-7）、无虚构端点、四态完整、错误处理友好。
- **冲突面**：暂无已知跨 Agent 冲突；T6.10.2/T6.10.3 同改 admin-web 须串行合并。
