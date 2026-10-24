# F3.2 — miniapp 类型检查门禁 · 实施方案

> Feature ID：F3.2
> 作者：frontend-engineer
> 日期：2026-09-29
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## 1. Root Cause

两个独立问题叠加：

1. **构建链路无门禁**：`build:mp-weixin` 直接 `uni build`，类型错误不阻断出包。
2. **API 数据边界缺类型**：`request<T>` 的多数调用未传类型实参，`res.data` 退化为 `unknown`（报错呈现为 `{}`），页面直接取字段即 TS2339；另有平台类型可空（TS18048）、组件契约漏声明（TS2769）、领域联合滞后于代码（TS2322）、第三方 d.ts 缺陷（PATCH）、泛型 Promise 递归丢类型（TS2345）六类根因。

门禁若直接开启会恒定红灯，因此必须"先清零、再挂门禁"。

## 2. 错误分类表与修复策略

| 类别 | 数量 | 根因 | 策略（禁止 any 淹没） |
|------|------|------|----------------------|
| A. 第三方 d.ts 缺陷 | 1 | @dcloudio/types method 联合漏 PATCH | 对内 `HttpMethod` 精确联合（含 PATCH）；仅 uni.request 边界单行 `as UniCompatibleRequestMethod` + 注释；运行时零变化 |
| B. 泛型封装缺陷 | 1 | Promise 未标注泛型 + 递归 request 丢 T | `new Promise<ApiResponse<T>>`；重放调用显式 `request<T>` |
| C. API 响应 unknown | 14 | 消费端直接读 res.data 字段 | 在 API 层补 7 个后端契约 interface 并给 8 个方法传精确泛型，一处修复、页面零改动（teacher/form 6 条 + teacher/profile 1 条 + courses/index 2 条 + 3 处 booking_cancel_minutes + bookings items 3 处 + AiAssistant data 2 处中后两者计列） |
| D. 平台可空值 | 4 | `statusBarHeight: number \| undefined` 直接参与算术 | 使用点 `?? 0`，与 UI 语义一致（无状态栏设备按 0 高度） |
| E. 组件契约漏声明 | 1 | emit 了未声明事件 | defineEmits 补 `(e:"message-sent", payload:{userMessage:string; aiResponse:string})` |
| F. 领域联合不完整 | 2 | reasonType 联合落后于实际返回值 | 补 `"pending"` / `"frozen"`；不新增 switch case（避免改 UI 行为） |
| G. null/undefined 语义 | 1 | `Ref<number\|null>` 传入 `number?` 入参 | 调用前局部 const 固化 + truthy 收窄 |

### 2.1 新增类型清单（全部位于 `src/api/index.ts`，L27-125）

| 类型 | 对齐的后端事实源 | 消费方 |
|------|-----------------|--------|
| `HttpMethod` / `UniCompatibleRequestMethod` | 后端 PATCH 契约 + `@dcloudio/types .../base/request.d.ts:19` | request 封装 |
| `TenantSettings` | `tenant/service.py:21-24` `{booking_cancel_minutes, booking_advance_days}` | booking-confirm / bookings / schedule 三页 cancelMinutes |
| `TenantInfo` | `tenant/service.py:34-41` 6 字段 | courses/index 租户名 |
| `AiChatMessage` | `modules/ai/router.py:89-98` history data 元素 `{role,content,timestamp}`，role 限 user/assistant | AiAssistant 历史加载 |
| `AiChatResult` | `modules/ai/router.py:70-80` chat data 5 字段 | AiAssistant 发送对话 |
| `ScheduleDetail` | `schedule/schemas.py:55-87` ScheduleResponse 全字段（id/public_id/.../course_type_code，时间序列化为 string） | teacher/schedule/form 回填 + booking-confirm（赋给 any ref） |
| `TeacherListItem` | `GET /teachers/` 列表元素，按页面实际消费取 id/nickname/avatar_url/title/specialties | courses/index 教师列表 |
| `TeacherStats` | teacher/profile 页面 stats 结构 `{courses,schedules,students}` | teacher/profile |
| 复用 `PaginatedData<T>` | F3.1 `src/utils/helpers.ts:7-12`，与后端 `{items,total,page,page_size}` 一致 | bookingApi.list |

### 2.2 被补泛型的 API 方法（8 处）

`bookingApi.list → PaginatedData<any>`、`scheduleApi.get → ScheduleDetail`、`teacherApi.list → TeacherListItem[]`、`teacherApi.getStats → TeacherStats`、`aiChatApi.chat → AiChatResult`、`aiChatApi.getHistory → AiChatMessage[]`、`tenantApi.getSettings → TenantSettings`、`tenantApi.getInfo → TenantInfo`。

未补泛型的方法保持原状：其消费方要么 `const x = res.data as any`（页面自有收敛），要么经 `extractList()`（入参声明为 `ApiResponse<PaginatedData<T>> | ApiResponse<T[]> | any`，天然兼容），补类型属无收益扩散。

## 3. 门禁设计

```jsonc
"type-check": "vue-tsc --noEmit",
"build:mp-weixin": "vue-tsc --noEmit && uni build -p mp-weixin",
"build:mp-weixin:dev": "vue-tsc --noEmit && uni build -p mp-weixin --mode development"
```

- 选 `&&` 串联而非独立 prebuild 钩子：脚本意图显式、跨平台（macOS / Linux / Windows sh 均支持）、CI 直接继承退出码。
- `--noEmit`：只检查不产 JS，产物唯一来源仍是 uni build，避免双份产物 / 路径污染。
- dev watch（`dev:mp-weixin`）与 h5 build 不挂门禁（见 requirement Out of Scope）。

## 4. Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/miniapp/package.json` | scripts：+1 个 type-check，2 个 mp-weixin build 前置 vue-tsc |
| 2 | `apps/miniapp/src/api/index.ts` | +1 type-only import；+8 个类型（2 type alias + 7 interface，L1/L27-125）；request 签名 method 改 HttpMethod（L203-205）；Promise 泛型化（L251）；method 边界断言（L257-258）；递归 `request<T>`（L274-275）；8 个 API 方法补泛型 |
| 3 | `apps/miniapp/src/components/AiAssistant.vue` | defineEmits +message-sent（L166-173）；history map 去 any 注解（L254） |
| 4 | `apps/miniapp/src/pages/student/booking-confirm/index.vue` | statusBarHeight `?? 0`（L255-257）；handleConfirm const cardId 收窄（L669-687） |
| 5 | `apps/miniapp/src/pages/student/bookings/index.vue` | statusBarHeight `?? 0`（L140-142） |
| 6 | `apps/miniapp/src/pages/student/courses/detail.vue` | statusBarHeight `?? 0`（L167-169） |
| 7 | `apps/miniapp/src/pages/student/schedule/index.vue` | reasonType 联合 +pending/frozen（L188-195）；statusBarHeight `?? 0`（L198-199） |

**经 API 层修复、页面零改动**：`student/courses/index.vue`、`teacher/profile/index.vue`、`teacher/schedule/form.vue`。

**工作区边界**：`membership/index.vue`、`teacher/schedule/index.vue`、`teacher/students/index.vue`、`static/icons/icon-map.ts` 及 AiAssistant / booking-confirm / schedule 三文件中的其余 hunk 为**前序 Feature（F3.1 等）未提交改动**，本 Feature 未触碰、未 commit、未 stash。

## 5. 实施顺序（先绿灯后挂门禁，避免中间态不可构建）

1. 冻结基线：记录 27 error 输出（requirement 分类表）。
2. 修 api/index.ts（A/B 两类 + 类型定义 + 8 方法泛型）。
3. 修 AiAssistant（E + 消费 C 类型）。
4. 修 4 页面 D 类 + F 类 + G 类。
5. `vue-tsc --noEmit` 迭代至 0 error。
6. 改 package.json 挂门禁。
7. 正向构建验证 → 反向探针验证 → 还原复核。
8. 交付文档 + backlog 关闭。

## 6. 风险控制

- 不改 tsconfig、不加依赖、不碰后端与其他端 → 爆炸半径限定在 miniapp 类型层。
- `?? 0` / 联合补全 / emit 签名 / const 收窄均为运行时等价或近等价改动（acceptance 第"行为等价性"节逐条说明）。
- 唯一 `as` 断言带注释且限定单行，评审可一眼识别；grep 可长期监控 `@ts-ignore` 数量保持 0。

## 7. 验证计划

- 静态：vue-tsc 0 error；grep 无 @ts-ignore；git diff 逐 hunk 人工核对（见 static-verification.md）。
- 运行时：门禁正/反两组 shell 级验证（见 runtime-test-report.md）。
