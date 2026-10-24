# F3.2 — miniapp 类型检查门禁 · 验收标准

> 验证目录：`cd apps/miniapp`
> 全部 AC 均可通过命令行复现，证据见 [static-verification.md](./static-verification.md) 与 [runtime-test-report.md](./runtime-test-report.md)。

| # | AC | 验证方式 | 预期（实测） |
|---|----|---------|-------------|
| AC-1 | 构建脚本前置类型门禁 | `cat package.json` 检查 scripts | `build:mp-weixin` == `vue-tsc --noEmit && uni build -p mp-weixin`；`build:mp-weixin:dev` == `vue-tsc --noEmit && uni build -p mp-weixin --mode development`；新增 `type-check: vue-tsc --noEmit` |
| AC-2 | 全量类型检查 0 error | `npx vue-tsc --noEmit; echo $?` | 无任何输出，退出码 **0**（基线 27 error → 0） |
| AC-3 | 正向构建：先检查后出包 | `npm run build:mp-weixin` | 日志先无 vue-tsc 报错，随后出现"正在编译中… / DONE Build complete."；退出码 0；`dist/build/mp-weixin/` 含 app.js / app.json / App.wxml / pages/ 等产物 |
| AC-4 | 反向门禁：类型错误阻断构建且 uni build 不执行 | 临时写入探针 `src/__type_gate_probe.ts`（`const probeValue: number = "bad"`）后执行 `npm run build:mp-weixin` | 输出 `error TS2322`；整体退出码 **2**；日志中"正在编译中"出现次数 **0**（`&&` 短路证明）；删除探针并恢复后 vue-tsc 回到退出码 0 |
| AC-5 | 修复手段合规（无静默淹没） | `grep -rn "@ts-ignore\|@ts-nocheck" src/` | 0 匹配（改前亦 0，新增亦 0）；全仓 `as` 新增仅 1 处：`method as UniCompatibleRequestMethod`（PATCH 第三方类型缺陷，单行 + 注释）；tsconfig strict 未改、无新依赖 |
| AC-6 | F3.1 回归不破坏 | 静态 grep + vue-tsc | `src/utils/helpers.ts` 仍导出 `extractList`；5 个 F3.1 页面的 `extractList` / `tenantApi` import 保持；vue-tsc 全量 0 error（F3.1 页面均在检查范围内） |
| AC-7 | 修复以正确类型为主而非 any | 代码审查 | 7 个新增 interface 均对齐后端真实响应字段（TenantService / ai router / ScheduleResponse / BookingListResponse）；4 处 `?? 0`、1 处联合补全、1 处 const 收窄、1 处 emit 签名补全；无大面积 `as any`（新增 `as any` 数量 0） |
| AC-8 | 范围约束 | `git status --short apps/miniapp` | 仅 7 文件被 F3.2 修改（package.json、api/index.ts、AiAssistant.vue、4 个 student 页面）；teacher/profile、teacher/schedule/form、student/courses/index 的错误经由 API 层类型修复，**页面文件本身 0 改动**；后端与其他三端 0 改动 |

## 27 个存量错误逐条核销表

| # | 位置（改前） | 错误码 | 修复方式 | 核销 |
|---|-------------|--------|---------|------|
| 1 | api/index.ts (155,9) | TS2769 | `HttpMethod` 联合 + uni.request 边界单行断言 | ✅ |
| 2 | api/index.ts (179,25) | TS2345 | `new Promise<ApiResponse<T>>` + 递归调用显式 `request<T>` | ✅ |
| 3 | AiAssistant.vue (250,41) | TS2339 | `getHistory` 泛型化为 `AiChatMessage[]` | ✅ |
| 4 | AiAssistant.vue (282,19) | TS2339 | `chat` 泛型化为 `AiChatResult` | ✅ |
| 5 | AiAssistant.vue (290,12) | TS2769 | defineEmits 补 `message-sent` 签名 | ✅ |
| 6 | booking-confirm (256,22) | TS18048 | `(statusBarHeight ?? 0) + 44` | ✅ |
| 7 | booking-confirm (683,13) | TS2322 | 局部 `const cardId` 收窄 null | ✅ |
| 8 | booking-confirm (720,50) | TS2339 | `tenantApi.getSettings(): TenantSettings` | ✅ |
| 9 | bookings (141,22) | TS18048 | `?? 0` | ✅ |
| 10 | bookings (165,50) | TS2339 | TenantSettings 泛型 | ✅ |
| 11-13 | bookings (204,18)(204,49)(205,31) | TS2339 | `bookingApi.list(): PaginatedData<any>` | ✅ |
| 14 | courses/detail (168,3) | TS18048 | `?? 0` | ✅ |
| 15 | courses/index (318,38) | TS2339 | `tenantApi.getInfo(): TenantInfo` | ✅ |
| 16 | courses/index (337,7) | TS2740 | `teacherApi.list(): TeacherListItem[]` | ✅ |
| 17 | schedule/index (197,22) | TS18048 | `?? 0` | ✅ |
| 18 | schedule/index (396,9) | TS2322 | reasonType 联合补 `"pending"` | ✅ |
| 19 | schedule/index (406,9) | TS2322 | reasonType 联合补 `"frozen"` | ✅ |
| 20 | schedule/index (572,50) | TS2339 | TenantSettings 泛型 | ✅ |
| 21 | teacher/profile (113,5) | TS2322 | `teacherApi.getStats(): TeacherStats` | ✅ |
| 22-27 | teacher/schedule/form (193,36)(193,62)(195,34)(196,32)(201,23)(202,20) | TS18046 | `scheduleApi.get(): ScheduleDetail`（6 条同根因，一次修复） | ✅ |

合计 27/27 核销，修复后实测 0 error。

## 行为等价性说明

- 所有修改均为**类型层**：interface / 泛型参数 / `?? 0`（statusBarHeight 为 undefined 时原表达式得 NaN，`?? 0` 后得 44，仅影响原本就异常的边界环境，正常设备数值完全一致）/ 联合补全（不改 switch 分支）/ emit 签名（运行时派发本就存在）。
- 唯一可能的运行时差异点：`booking-confirm` 的 `const cardId = selectedCardId.value` —— 值与读取时机完全一致（同一 tick、弹窗回调前读取），仅用于类型收窄，逻辑等价。
- PATCH 断言为编译期语法，JS 产出中 method 字符串原样透传。
