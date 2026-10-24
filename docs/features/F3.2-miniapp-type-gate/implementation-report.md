# F3.2 — miniapp 类型检查门禁 · 实施报告

> 日期：2026-09-29 ｜ 执行：frontend-engineer
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

按计划"先清零、再挂门禁"顺序一次交付：`src/api/index.ts` 新增 2 个 type alias + 7 个对齐后端契约的 interface、修复 PATCH 联合与递归泛型、给 8 个 API 方法补精确泛型；`AiAssistant.vue` 补 emit 契约；4 个 student 页面 5 处定点修改（statusBarHeight ×4、reasonType 联合、const 收窄）。vue-tsc 首轮迭代后 **27 error → 0 error**；`package.json` 两个 mp-weixin 出包脚本前置 `vue-tsc --noEmit &&`，并新增 `type-check` 脚本。正向 `npm run build:mp-weixin` 完整出包成功（`dist/build/mp-weixin/`），反向探针验证退出码 2 且 uni build 被 `&&` 短路。零新增依赖、零 tsconfig 改动、零 @ts-ignore、零业务/UI/后端改动。T3.2.1 / T3.2.2 全部交付。

## 2. 逐文件改动明细

### 2.1 `apps/miniapp/package.json`（scripts，L5-12）

```diff
     "dev:mp-weixin": "uni -p mp-weixin",
+    "type-check": "vue-tsc --noEmit",
-    "build:mp-weixin": "uni build -p mp-weixin",
-    "build:mp-weixin:dev": "uni build -p mp-weixin --mode development"
+    "build:mp-weixin": "vue-tsc --noEmit && uni build -p mp-weixin",
+    "build:mp-weixin:dev": "vue-tsc --noEmit && uni build -p mp-weixin --mode development"
```

- dev:* 与 build:h5 未动（范围外）。

### 2.2 `apps/miniapp/src/api/index.ts`（核心，净增约 110 行类型 + 6 处定点）

**(a) 复用 F3.1 类型（L1）**

```ts
import type { PaginatedData } from "@/utils/helpers";
```

type-only 引用；helpers.ts 不反向依赖 api 层，无循环依赖。

**(b) HttpMethod 与第三方兼容联合（L27-46）**

```ts
type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
type UniCompatibleRequestMethod =
  | "OPTIONS" | "GET" | "HEAD" | "POST" | "PUT"
  | "DELETE" | "TRACE" | "CONNECT";
```

`HttpMethod` 上方附块注释，说明后端契约含 PATCH、@dcloudio/types `RequestOptions.method`（`uni/base/request.d.ts:19`）漏声明、运行时透传可用、断言仅限调用边界。

**(c) 7 个 export interface（L48-125）**：`TenantSettings` / `TenantInfo` / `AiChatMessage` / `AiChatResult` / `ScheduleDetail` / `TeacherListItem` / `TeacherStats`，字段逐一核对后端（来源见 plan 2.1）。其中 `AiChatMessage.role` 收窄为 `"user" | "assistant"`，使 AiAssistant 内部 `Message` 接口无需 any 即可赋值。

**(d) request 封装三处（L203 / L251 / L257-258 / L274-275）**

```diff
-async function request<T>(
+async function request<T>(
   url: string,
-  method: "GET" | "POST" | "PATCH" | "DELETE" = "GET",
+  method: HttpMethod = "GET",
...
-    new Promise((resolve, reject) => {
+    new Promise<ApiResponse<T>>((resolve, reject) => {
...
-        method,
+        // 第三方 @dcloudio/types 联合漏 PATCH，见 HttpMethod 注释；局部断言、运行时原样透传
+        method: method as UniCompatibleRequestMethod,
...
-                const retryResult = await request(
+                // 显式透传泛型 T，保证重放请求与原请求响应类型一致
+                const retryResult = await request<T>(
```

- TS2769（PATCH）与 TS2345（resolve unknown→T）双消；`withTimeout` 推导链维持 `Promise<ApiResponse<T>>`。

**(e) 8 个方法补泛型实参**

| 方法（当前行号） | 泛型 |
|------------------|------|
| `bookingApi.list` (L513) | `request<PaginatedData<any>>`（items 元素仍为 any——booking 元素类型体系庞大，本 Feature 不展开，门禁目标是消除 unknown 级错误而非全量建模） |
| `scheduleApi.get` (L493) | `request<ScheduleDetail>` |
| `teacherApi.list` (L567) | `request<TeacherListItem[]>` |
| `teacherApi.getStats` (L562-564) | `request<TeacherStats>`（附注释：端点现指向 /auth/me 的语义差异为既有实现，本 Feature 仅补类型） |
| `aiChatApi.chat` (L599) | `request<AiChatResult>` |
| `aiChatApi.getHistory` (L610) | `request<AiChatMessage[]>` |
| `tenantApi.getSettings` (L647) | `request<TenantSettings>` |
| `tenantApi.getInfo` (L650) | `request<TenantInfo>` |

### 2.3 `apps/miniapp/src/components/AiAssistant.vue`（2 处）

- L166-173：`defineEmits` 补第三成员：
  ```ts
  (e: "message-sent", payload: {
    userMessage: string;
    aiResponse: string;
  }): void;
  ```
- L254：`(res.data || []).map((msg) => ...)` 去掉 `(msg: any)` 注解——`getHistory` 现返回 `AiChatMessage[]`，msg 自动推导，`msg.role` 恰为组件 `Message.role` 的 `"user"|"assistant"` 联合。
- L282 `res.data?.response` 与 L290 `emit("message-sent", ...)` 无需再改：前者经 `AiChatResult` 泛型合法，后者经新签名合法。
- 注：该文件在工作区含前序未提交的大量样式/模板改动（git diff 392 行中的绝大部分），F3.2 仅上述 2 个 script hunk。

### 2.4 `apps/miniapp/src/pages/student/booking-confirm/index.vue`（2 处）

- L255-257：`const navbarHeight = (systemInfo.statusBarHeight ?? 0) + 44;`（+1 行注释）。
- L669-687：handleConfirm 开头把 `selectedCardId.value`（`number | null`）固化进局部 `cardId`，truthy 守卫后以 `cardId: number` 传入 `bookingApi.create({ membership_card_id })`；消除弹窗回调内的类型收窄失效（TS2322）。读取时机与值完全等价。
- L720 `booking_cancel_minutes` 错误经 `TenantSettings` 泛型消除，页面该行未改。

### 2.5 `apps/miniapp/src/pages/student/bookings/index.vue`（1 处）

- L140-142：statusBarHeight `?? 0`（+注释）。
- L165 tenant 配置、L204-205 `rawData.items` 两类错误经 API 泛型消除：`rawData` 现为 `PaginatedData<any>`，页面既有的 `Array.isArray` / 对象兜底分支全部保持原样且类型合法（array 分支收窄为 never，赋给 `any[]` 合法）。

### 2.6 `apps/miniapp/src/pages/student/courses/detail.vue`（1 处）

- L167-169：`(systemInfo.statusBarHeight ?? 0) + Math.max(menuButton.height + 10, 44)`。

### 2.7 `apps/miniapp/src/pages/student/schedule/index.vue`（2 处）

- L188-195：`CardValidationResult.reasonType` 联合追加 `"pending" | "frozen"`，与同文件 L395/L405 两个实际返回点对齐。
- L198-199：statusBarHeight `?? 0`。
- L572 tenant 配置错误经泛型消除。switch 未加 pending/frozen case——运行时仍走既有 default 分支（行为零变化，UI 优化不在范围）。

### 2.8 页面零改动（由 API 层类型直接修复）

- `student/courses/index.vue`：L318 `.name`（TenantInfo）、L337 数组赋值（TeacherListItem[]）。
- `teacher/profile/index.vue`：L113 `stats.value = result.data`（TeacherStats，结构与 stats ref 一致）。
- `teacher/schedule/form.vue`：6 条 TS18046（`schedule.course_id/course_name/start_at/end_at/capacity/notes`）随 ScheduleDetail 全部消除；`notes: string | null` 经既有 `|| ''` 兜底，类型合法。

## 3. 与计划的偏差

- 计划中"4 个 student 页面 5 处定点修改"与实际一致；额外新增了 `type-check` 脚本（计划门禁设计节已列，非范围外扩张）。
- `build:mp-weixin:dev` 同步挂门禁（计划已声明：同为 mp-weixin 出包链路）。
- 其余无偏差；未新增任何计划外源文件，探针文件 `src/__type_gate_probe.ts` 验证后已删除。

## 4. 工作区边界与既有改动保护

- F3.2 实际触达 7 个文件（见 plan 第 4 节）。
- `git status` 中 `student/membership/index.vue`、`teacher/schedule/index.vue`、`teacher/students/index.vue`、`static/icons/icon-map.ts` 为 F3.1 等前序未提交改动，本 Feature 零触碰；AiAssistant / booking-confirm / schedule 三文件中的前序 hunk 通过 diff 逐段核对，F3.2 仅插入本报告列出的定点 hunk。
- 未执行 git commit / stash / reset 等任何操作。

## 5. 数据 / 契约兼容

- 无后端、OpenAPI、DB、Redis、环境变量改动；无新依赖（vue-tsc / typescript 均为 devDependencies 既有）。
- 网络请求行为零变化：method 字符串、URL、header、重放逻辑全部保持；断言仅存在于 tsc 编译期。
- 三端（admin / student / teacher web）与 miniapp 的接口调用集合无变化。

## 6. 测试结果

- `npx vue-tsc --noEmit`：**0 error**（基线 27），退出码 0。
- 正向：`npm run build:mp-weixin` → `DONE Build complete.`，dist 产物完整，退出码 0。
- 反向：探针 TS2322 → 退出码 2，uni build 执行次数 0；删除探针后恢复退出码 0。
- 静态：`grep -rn "@ts-ignore|@ts-nocheck" src/` → 0 匹配；新增 `as any` 0 处；唯一 `as` 为带注释的 PATCH 边界断言。

详见 [static-verification.md](./static-verification.md) 与 [runtime-test-report.md](./runtime-test-report.md)。
