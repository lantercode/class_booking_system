# F3.2 — miniapp 类型检查门禁 · 需求文档

> Feature ID：F3.2
> 作者：frontend-engineer
> 日期：2026-09-29
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（纯前端工程化 Feature，仅触达 `apps/miniapp`，不召后端 / DB / MCP）
> 依赖：无（`vue-tsc ^2.2.0`、`typescript ^5.4.5` 已在 devDependencies 且 node_modules 已安装；F3.1 产物 `src/utils/helpers.ts` 的 `PaginatedData<T>` 可直接复用）
> 前置 Feature：F3.1（miniapp 崩溃修复，已完成；本 Feature 不破坏其补全的 `extractList` / `tenantApi` import）

---

## Goal

miniapp（uni-app + Vue3 + TS）当前构建脚本 `build:mp-weixin` 为裸 `uni build -p mp-weixin`，**构建前不做任何类型检查**；同时仓库存量 `npx vue-tsc --noEmit` 有 **27 个 TS 错误**。这意味着类型错误可以静默流入微信小程序生产包，只在运行时以白屏 / `undefined` 读取异常的形式暴露（F3.1 修复的页面崩溃即同类问题的下游表现）。

修复目标：

1. 在 mp-weixin 构建链路前置 `vue-tsc --noEmit` 强制门禁：类型错误非零退出时 `uni build` 不得执行，产物不得产出。
2. 将存量 27 个类型错误以**正确类型**修复到 0，使门禁可实际开启——不以 `any` 淹没、不放松 tsconfig、不用全局 `@ts-ignore`。

## User Story

作为维护 miniapp 的前端工程师，

- 我希望执行 `npm run build:mp-weixin` 时先跑全量 vue-tsc：我本地有类型错误时构建立即中止并打印错误，而不是打出一个运行时才崩的包。
- 我希望 API 响应在 API 层就有与后端契约一致的类型（租户配置、分页结构、排期详情、AI 对话响应等），页面消费 `res.data` 时能获得字段提示与编译期检查，而不是面对 `{}` / `unknown`。
- 我希望门禁是"零新增心智负担"的：不新增依赖、不改 tsconfig strict、不改任何业务逻辑与 UI；存量错误修完后日常开发只需保持 0 error。

作为发布流程（系统），

- 我希望任何 CI / 人工执行的 mp-weixin 构建都被同一道门禁拦截：`vue-tsc` 退出码非 0 → `&&` 短路 → 进程退出码非 0 → CI 红灯 / 无产物。

## Background / 现状（已核查的代码事实）

| # | 事实 | 证据 |
|---|------|------|
| 1 | 构建脚本无类型门禁 | `apps/miniapp/package.json` L9（改前）：`"build:mp-weixin": "uni build -p mp-weixin"` |
| 2 | 类型检查工具链已就绪 | package.json devDependencies 含 `vue-tsc ^2.2.0`、`typescript ^5.4.5`、`@dcloudio/types ^3.4.8`，node_modules 已安装，无需新增依赖 |
| 3 | 存量基线为 27 error | `cd apps/miniapp && npx vue-tsc --noEmit` 实测输出 27 条（2026-09-29） |
| 4 | 无既有业务类型目录 | `src/types/` 不存在；仅 F3.1 在 `src/utils/helpers.ts` 提供 `ApiResponse<T>` / `PaginatedData<T>`（{items,total,page,page_size}） |
| 5 | 错误根因集中在 API 层泛型缺失 | `request<T>` 无默认泛型、调用方多数未传类型实参 → `res.data` 推断为 `unknown`（报错信息呈现为 `{}`），页面取字段即 TS2339 |
| 6 | 第三方类型缺陷 1 处 | `@dcloudio/types` 的 `RequestOptions.method` 内联联合为 `'OPTIONS'\|'GET'\|'HEAD'\|'POST'\|'PUT'\|'DELETE'\|'TRACE'\|'CONNECT'`（`node_modules/@dcloudio/types/uni-app/uni/base/request.d.ts:19`），**漏声明 PATCH**；而后端 users / courses / schedules / teachers 更新接口契约均为 PATCH（见 `apps/miniapp/src/api/index.ts` 各 `request(..., "PATCH", ...)` 调用），不能删动词 |
| 7 | 泛型 Promise 封装缺陷 | 改前 `new Promise((resolve, reject) => ...)` 未标注泛型，401 重放分支递归调用 `request(...)` 未透传 `<T>` → `resolve(retryResult)` 处 `ApiResponse<unknown>` 不可赋给 `ApiResponse<T>`（TS2345） |
| 8 | 平台可空字段 | `uni.getSystemInfoSync().statusBarHeight: number | undefined`（@dcloudio/types），4 个页面直接 `+ 44` 触发 TS18048 |
| 9 | 组件契约漏声明 | `AiAssistant.vue` 实际 `emit("message-sent", ...)` 但 `defineEmits` 仅声明 booking-created / booking-cancelled（TS2769） |
| 10 | 状态联合不完整 | `student/schedule/index.vue` 的 `CardValidationResult.reasonType` 联合仅 5 值，代码实际返回 `"pending"` / `"frozen"`（会员卡 status=0 未激活 / status=3 冻结） |

### 27 个错误分布（基线）

| 文件 | 数量 | 错误码 / 位置 |
|------|------|---------------|
| `src/api/index.ts` | 2 | TS2769 (155,9) method 联合含 PATCH；TS2345 (179,25) 递归 resolve 泛型不一致 |
| `src/components/AiAssistant.vue` | 3 | TS2339 (250,41) `{}.map`；TS2339 (282,19) `{}.response`；TS2769 (290,12) 未声明 message-sent |
| `student/booking-confirm/index.vue` | 3 | TS18048 (256,22) statusBarHeight；TS2322 (683,13) `number\|null` → `number\|undefined`；TS2339 (720,50) `{}.booking_cancel_minutes` |
| `student/bookings/index.vue` | 5 | TS18048 (141,22)；TS2339 (165,50) booking_cancel_minutes；TS2339 (204,18)(204,49)(205,31) `{}.items` |
| `student/courses/index.vue` | 2 | TS2339 (318,38) `{}.name`；TS2740 (337,7) `{}` 不可赋数组 |
| `student/courses/detail.vue` | 1 | TS18048 (168,3) statusBarHeight |
| `student/schedule/index.vue` | 4 | TS18048 (197,22)；TS2322 (396,9)(406,9) 联合缺 pending/frozen；TS2339 (572,50) booking_cancel_minutes |
| `teacher/profile/index.vue` | 1 | TS2322 (113,5) unknown 不可赋 stats 对象 |
| `teacher/schedule/form.vue` | 6 | TS18046 (193,36)(193,62)(195,34)(196,32)(201,23)(202,20) `schedule` unknown 取属性 |

## Scope（In Scope）

1. **T3.2.1 门禁**：`package.json` 的 `build:mp-weixin` 改为 `vue-tsc --noEmit && uni build -p mp-weixin`；同构的 `build:mp-weixin:dev` 一并加门禁（同为 mp-weixin 出包脚本，避免 dev 模式出包绕过检查）；新增便捷脚本 `type-check`。
2. **T3.2.2 清零 27 个存量错误**，全部以正确类型修复：
   - `src/api/index.ts`：补最小必要业务类型（复用 `PaginatedData<T>`，新增 TenantSettings / TenantInfo / AiChatMessage / AiChatResult / ScheduleDetail / TeacherListItem / TeacherStats），给被消费 data 的 API 方法补精确泛型；修 PATCH 联合与递归泛型；
   - 4 处 statusBarHeight `?? 0`；
   - AiAssistant 补 `message-sent` emit 签名；
   - schedule reasonType 联合补 `pending` / `frozen`；
   - booking-confirm 以局部 const 收窄 `number | null`。

## Out of Scope

- 不改后端（FastAPI）、不改 admin-web / student-web / teacher-web 三端、不改 MCP。
- 不改任何业务逻辑、接口调用、UI 渲染、文案与样式（纯类型层 + 构建脚本）。
- 不放松 `tsconfig` strict 系列选项；不新增依赖；不新增全局 `@ts-ignore` / `@ts-nocheck`。
- 不给所有 `request(...)` 调用一刀切补类型：仅给"页面直接消费 `data` 具体字段"的方法补泛型；其余经 `as any` 或 `extractList`（其入参签名本就兼容任意响应）消费的调用点保持原状，避免无意义扩散。
- 不门禁 `build:h5` / `dev:*`（dev 为热更新开发服务，AC 仅要求 mp-weixin 构建；h5 是否同策略留待后续决策，见 review 遗留事项）。
- 不修复 `teacherApi.getStats()` 端点指向 `/auth/me` 与统计语义不符的**既有业务问题**（只按页面消费结构补类型，问题登记 Risks，由后端 / 产品另立 Feature）。
- schedule 页面 `reasonType` 为 pending/frozen 时 switch default 显示"可预约"的**既有 UI 行为**不在本 Feature 修改（仅补类型联合，运行时分支零变化）。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1：`apps/miniapp/package.json` 的 `build:mp-weixin`（及 `build:mp-weixin:dev`）为 `vue-tsc --noEmit && uni build ...`。
- AC-2：`cd apps/miniapp && npx vue-tsc --noEmit` 退出码 0、0 error（基线 27 → 0）。
- AC-3：正向——`npm run build:mp-weixin` 先跑 vue-tsc 通过后执行 `uni build -p mp-weixin`，`dist/build/mp-weixin/` 正常产出。
- AC-4：反向——人为注入任一 TS 错误时，`npm run build:mp-weixin` 退出码非 0，输出 vue-tsc 错误，且 `uni build`（"正在编译中"）不执行；移除错误后恢复 0 error。
- AC-5：静态——src 全目录无新增 `@ts-ignore` / `@ts-nocheck`；唯一一处 `as` 断言为 PATCH 第三方类型缺陷的单行局部断言且带注释。
- AC-6：回归——F3.1 补全的 import（`extractList` / `tenantApi`）保持可用；vue-tsc 对全量文件 0 error。

## Dependencies

- 复用：`vue-tsc` / `typescript`（devDependencies 既有）；`@/utils/helpers` 的 `PaginatedData<T>`（F3.1 既有，type-only import，无运行时循环依赖风险：helpers.ts 不 import api 层）。
- 类型契约依据（只读核对，不改后端）：
  - `modules/tenant/service.py`：`get_settings` → `{booking_cancel_minutes, booking_advance_days}`；`get_tenant_info` → `{id,name,slug,logo_url,contact_phone,contact_email}`；
  - `modules/ai/router.py`：`POST /ai/chat` data 含 `response/session_id/timestamp/has_pending_state/latency_ms`；`GET /ai/history` data 为 `[{role,content,timestamp}]`；
  - `modules/schedule/schemas.py` `ScheduleResponse` 全字段；
  - `modules/booking/service.py` 列表返回 `BookingListResponse{total,page,page_size,items}`。
- 无后端接口变更、无 OpenAPI 变更、无 DB / Redis / 配置变更、无新依赖。

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 微信小程序运行时对 PATCH 的支持程度 | @dcloudio/types 与 wx 文档的 method 列表均不含 PATCH，但 uni.request 在 mp-weixin 平台透传 method 字符串，且仓库 users/courses/schedules/teachers 更新接口**既有调用全部依赖 PATCH**（保留 PATCH 是不改后端契约的硬约束）；本 Feature 仅做类型层局部断言，运行时行为零变化。PATCH 的真机可用性属既有实现的既成事实，建议后端/客户端联调时持续覆盖（见 Risks） |
| U2 | `teacherApi.getStats()` 指向 `/auth/me`，返回用户对象而非 `{courses,schedules,students}` 统计 | 存量实现与本 Feature 无关；按"不改业务逻辑"原则仅按页面消费结构声明 `TeacherStats` 类型（页面模板有 `\|\| 0` 兜底）。语义对齐需后端补真实统计端点或前端改接，登记 Risks R2，另立 Feature |
| U3 | CI 是否已接 `npm run build:mp-weixin` | 本 Feature 交付的是本地 / CI 统一可用的脚本门禁（退出码语义正确）；仓库 CI 配置是否调用该脚本未在本次范围内核查，登记为后续接入项（见 review 遗留事项 D-F3.2-2） |
