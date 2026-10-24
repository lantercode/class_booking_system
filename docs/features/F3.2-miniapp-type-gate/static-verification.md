# F3.2 — 静态验证报告

> 日期：2026-09-29 ｜ 执行：frontend-engineer
> 工作目录：`apps/miniapp`

## 1. 错误数前后对比：27 → 0

### 1.1 Before（F3.2 改动前基线，2026-09-29）

命令：`npx vue-tsc --noEmit`
退出码：非 0；共 **27 error**。原始输出：

```text
src/api/index.ts(155,9): error TS2769: No overload matches this call.
  Overload 1 of 2, '(options: RequestOptions): Promise<RequestSuccessCallbackResult>', gave the following error.
    Type '"GET" | "POST" | "PATCH" | "DELETE"' is not assignable to type '"GET" | "POST" | "DELETE" | "OPTIONS" | "HEAD" | "PUT" | "TRACE" | "CONNECT" | undefined'.
      Type '"PATCH"' is not assignable to type '"GET" | "POST" | "DELETE" | "OPTIONS" | "HEAD" | "PUT" | "TRACE" | "CONNECT" | undefined'.
  Overload 2 of 2, '(options: RequestOptions): RequestTask', gave the following error.
    Type '"GET" | "POST" | "PATCH" | "DELETE"' is not assignable to type '"GET" | "POST" | "DELETE" | "OPTIONS" | "HEAD" | "PUT" | "TRACE" | "CONNECT" | undefined'.
src/api/index.ts(179,25): error TS2345: Argument of type 'ApiResponse<unknown>' is not assignable to parameter of type 'ApiResponse<T> | PromiseLike<ApiResponse<T>>'.
src/components/AiAssistant.vue(250,41): error TS2339: Property 'map' does not exist on type '{}'.
src/components/AiAssistant.vue(282,19): error TS2339: Property 'response' does not exist on type '{}'.
src/components/AiAssistant.vue(290,12): error TS2769: No overload matches this call.
    Argument of type '"message-sent"' is not assignable to parameter of type '"booking-created"'.
    Argument of type '"message-sent"' is not assignable to parameter of type '"booking-cancelled"'.
src/pages/student/booking-confirm/index.vue(256,22): error TS18048: 'systemInfo.statusBarHeight' is possibly 'undefined'.
src/pages/student/booking-confirm/index.vue(683,13): error TS2322: Type 'number | null' is not assignable to type 'number | undefined'.
src/pages/student/booking-confirm/index.vue(720,50): error TS2339: Property 'booking_cancel_minutes' does not exist on type '{}'.
src/pages/student/bookings/index.vue(141,22): error TS18048: 'systemInfo.statusBarHeight' is possibly 'undefined'.
src/pages/student/bookings/index.vue(165,50): error TS2339: Property 'booking_cancel_minutes' does not exist on type '{}'.
src/pages/student/bookings/index.vue(204,18): error TS2339: Property 'items' does not exist on type '{}'.
src/pages/student/bookings/index.vue(204,49): error TS2339: Property 'items' does not exist on type '{}'.
src/pages/student/bookings/index.vue(205,31): error TS2339: Property 'items' does not exist on type '{}'.
src/pages/student/courses/detail.vue(168,3): error TS18048: 'systemInfo.statusBarHeight' is possibly 'undefined'.
src/pages/student/courses/index.vue(318,38): error TS2339: Property 'name' does not exist on type '{}'.
src/pages/student/courses/index.vue(337,7): error TS2740: Type '{}' is missing the following properties from type 'any[]': length, pop, push, concat, and 35 more.
src/pages/student/schedule/index.vue(197,22): error TS18048: 'systemInfo.statusBarHeight' is possibly 'undefined'.
src/pages/student/schedule/index.vue(396,9): error TS2322: Type '"pending"' is not assignable to type '"expired" | "no_card" | "not_applicable" | "insufficient" | "weekly_limit" | undefined'.
src/pages/student/schedule/index.vue(406,9): error TS2322: Type '"frozen"' is not assignable to type '"expired" | "no_card" | "not_applicable" | "insufficient" | "weekly_limit" | undefined'.
src/pages/student/schedule/index.vue(572,50): error TS2339: Property 'booking_cancel_minutes' does not exist type '{}'.
src/pages/teacher/profile/index.vue(113,5): error TS2322: Type 'unknown' is not assignable to type '{ courses: number; schedules: number; students: number; } | ...'.
src/pages/teacher/schedule/form.vue(193,36): error TS18046: 'schedule' is of type 'unknown'.
src/pages/teacher/schedule/form.vue(193,62): error TS18046: 'schedule' is of type 'unknown'.
src/pages/teacher/schedule/form.vue(195,34): error TS18046: 'schedule' is of type 'unknown'.
src/pages/teacher/schedule/form.vue(196,32): error TS18046: 'schedule' is of type 'unknown'.
src/pages/teacher/schedule/form.vue(201,23): error TS18046: 'schedule' is of type 'unknown'.
src/pages/teacher/schedule/form.vue(202,20): error TS18046: 'schedule' is of type 'unknown'.
```

（27 条；分类与核销见 [acceptance.md](./acceptance.md) 第 2 节。）

### 1.2 After（F3.2 改动后）

命令：

```bash
cd apps/miniapp && npx vue-tsc --noEmit; echo "VUE_TSC_EXIT=$?"
```

实测输出：

```text
VUE_TSC_EXIT=0
```

无任何诊断行，退出码 **0**。错误数 **27 → 0**。

## 2. package.json 门禁落地

`cat apps/miniapp/package.json` scripts 段实测：

```json
"scripts": {
    "dev:h5": "uni",
    "build:h5": "uni build",
    "dev:mp-weixin": "uni -p mp-weixin",
    "type-check": "vue-tsc --noEmit",
    "build:mp-weixin": "vue-tsc --noEmit && uni build -p mp-weixin",
    "build:mp-weixin:dev": "vue-tsc --noEmit && uni build -p mp-weixin --mode development"
}
```

## 3. 修复手段合规性 grep

### 3.1 无 ts-ignore / ts-nocheck

命令：`grep -rn "@ts-ignore\|@ts-nocheck" src/ || echo NONE_FOUND`

实测：

```text
NONE_FOUND
```

改前基线同为 0（未以静默方式压错）。

### 3.2 断言使用审计

命令：`grep -rn " as " src/api/index.ts`

新增断言仅 1 处（L258）：

```ts
// 第三方 @dcloudio/types 联合漏 PATCH，见 HttpMethod 注释；局部断言、运行时原样透传
method: method as UniCompatibleRequestMethod,
```

- 断言目标类型为与第三方 d.ts 逐字一致的联合；源类型 `HttpMethod` 与其有 4 个共有成员，属于合法的重叠断言（非双重断言、非 as any）。
- 全 Feature 新增 `as any`：**0 处**。

### 3.3 tsconfig / 依赖零变化

- 未修改 `tsconfig.json`（strict 仍开启，未通过关松配置消错）。
- package.json dependencies / devDependencies 版本与条目零变化；仅 scripts 变化。

## 4. F3.1 回归静态确认

```text
$ grep -n "extractList" src/utils/helpers.ts        # 定义仍在 L29
$ grep -rn "from \"@/utils/helpers\"" src/pages | wc -l   # 5 个 F3.1 页面 import 保持
$ grep -n "tenantApi" src/api/index.ts              # 导出仍在（L645），仅方法补泛型
```

vue-tsc 全量 0 error 已覆盖以下 F3.1 相关文件（编译期 import 解析全部通过）：
`teacher/schedule/index.vue`、`teacher/students/index.vue`、`student/schedule/index.vue`、`teacher/schedule/form.vue`、`student/courses/detail.vue`、`student/courses/index.vue`、`student/courses/list.vue`。

## 5. 变更文件清单（F3.2 实际触达）

```text
apps/miniapp/package.json
apps/miniapp/src/api/index.ts
apps/miniapp/src/components/AiAssistant.vue
apps/miniapp/src/pages/student/booking-confirm/index.vue
apps/miniapp/src/pages/student/bookings/index.vue
apps/miniapp/src/pages/student/courses/detail.vue
apps/miniapp/src/pages/student/schedule/index.vue
```

经 API 层类型修复、页面本身零改动：`student/courses/index.vue`、`teacher/profile/index.vue`、`teacher/schedule/form.vue`。
后端（`apps/api/**`）与其他 web 三端：**0 改动**（git status 验证）。
临时探针 `src/__type_gate_probe.ts` 已删除，git status 无残留。

## 6. 静态验证结论

| 检查项 | 结果 |
|--------|------|
| vue-tsc 错误数 | 27 → **0** |
| vue-tsc 退出码 | **0** |
| @ts-ignore / @ts-nocheck | 0 |
| 新增 as any | 0 |
| 唯一 as 断言 | PATCH 边界单行 + 注释 |
| tsconfig strict | 未改动 |
| 新依赖 | 0 |
| 后端 / 其他端改动 | 0 |
| F3.1 import 回归 | 保持、全量编译通过 |
