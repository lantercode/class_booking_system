# F3.1 — miniapp 运行时崩溃修复 · 用户流程

> Feature ID：F3.1
> 说明：本 Feature 是 Bug 修复，不引入新流程。本文档描述修复后 3 个页面**应表现的完整流程**（含异常与边界场景），作为开发与验收的共同基准。
> 页面内既有逻辑（catch toast、isUnmounted 保护、checkLogin 鉴权）均为现状描述，本 Feature 不改动它们。

---

## 1. 教师排期页 `pages/teacher/schedule/index`

### 1.1 主流程（Happy Path）

1. 教师角色用户打开页面。
2. `onMounted` 触发 `checkLogin('teacher')` → 已登录且角色匹配，继续。
3. 从 `uni.getStorageSync('user_info')` 解析当前用户 ID（解析失败静默忽略，不阻断）。
4. 调用 `teacherApi.getSchedules({ start_from: 本周一, start_to: 本周日 })`。
5. 请求成功 → `extractList(result)` 将响应解析为排期数组写入 `schedules`。
6. 页面按"周 × 时间段"网格渲染本周排期。
7. 用户可执行既有交互：切换上一周/下一周（重新走第 4 步）、点击排期格查看详情弹层。

### 1.2 Loading

- 现状：页面无独立 loading 组件，数据返回前网格为空。
- 本 Feature 不补 loading 态（属 F3.4）。验收仅要求：数据返回期间页面不崩溃、不白屏卡死。

### 1.3 Error

- API 请求失败（网络错误 / 500 / 401 等）→ 进入 `catch` → `uni.showToast({ title: '加载失败', icon: 'none' })`，页面停留在空网格，不崩溃。
- 401 场景由小程序请求层统一处理（refresh → 重放 → 失败清登录态），页面不重复实现。

### 1.4 空状态

- 本周无排期（API 成功但返回空数组）→ `extractList` 返回 `[]` → 网格正常渲染为全空，无报错。
- 注意：`extractList` 对空响应/空 data 会打 `console.warn` 并返回 `[]`，属正常行为，不视为错误。

### 1.5 Success

- 排期数据正确渲染；切换周数据随之更新；点击排期格弹出详情。

### 1.6 Permission / Authentication

| 场景 | 预期行为 |
|------|---------|
| 未登录用户进入 | `checkLogin('teacher')` 拦截，跳转登录页，不发数据请求 |
| 学员角色用户进入 | `checkLogin('teacher')` 拦截（角色不匹配），不发数据请求 |
| Token 过期 | 请求层 401 refresh 链路处理；refresh 失败清登录态跳登录 |

---

## 2. 教师学员页 `pages/teacher/students/index`

### 2.1 主流程（Happy Path）

1. 教师角色用户打开页面。
2. `checkLogin('teacher')` 通过；解析 `user_info`（失败静默忽略）。
3. 调用 `teacherApi.getSchedules({ start_from: 今天, start_to: 今天, status: 1 })`。
4. `extractList(result)` 解析出今日进行中排期列表。
5. 若列表非空 → 默认选中第一个排期 → 调用 `bookingApi.list({ schedule_id })` → `extractList(result)` 解析出学员名单并渲染。
6. 用户可切换排期（重新加载学员名单）、查看学员预约状态（已预约/已签到/已完成/已取消）。

### 2.2 Loading

- 现状：无独立 loading 组件。名单加载期间列表为空，不崩溃即可（四态属 F3.4）。

### 2.3 Error

- 排期请求失败 → toast「加载失败」，排期列表为空，不触发学员名单请求，不崩溃。
- 学员名单请求失败 → toast「加载失败」，名单为空，不崩溃。
- 二次崩溃点说明：第 153 行的 `extractList` 在 `loadStudents` 内，只有第 134 行修复后才会执行到；两处必须同时修复，单独修一处页面仍然崩溃。

### 2.4 空状态

- 今日无进行中排期 → 排期列表为空，不请求学员名单，页面正常渲染空态，无报错。
- 选中的排期无预约 → 名单渲染为空，无报错。

### 2.5 Success

- 今日排期与学员名单正确渲染；切换排期名单随之更新；预约状态文案/样式正确。

### 2.6 Permission / Authentication

同 1.6（`checkLogin('teacher')`）。此外注意既有 P1-5 问题（`GET /bookings` 按 schedule_id 查询的越权风险）属于后端 Feature 2.2，**不在本 Feature 修复范围**，验收时不要求该接口已做归属收敛。

---

## 3. 学员排期页 `pages/student/schedule/index`

### 3.1 主流程（Happy Path）

1. 学员角色用户打开页面。
2. `checkLogin('student')` 通过；解析 `user_info`（失败静默忽略）。
3. 调用 `tenantApi.getSettings()` 加载租户配置（取消时限 `booking_cancel_minutes`），成功则覆盖默认值 90 分钟。
4. 选中今天日期，并行加载：课程类型（`courseTypeApi.list`）、当日排期（`loadSchedules`）、我的预约（`loadBookings`）、我的会员卡（`loadMembershipCards`）。
5. 页面渲染日期选择、课程类型筛选、当日排期列表（含剩余名额/约课按钮）。
6. 用户可执行既有交互：切换日期、按类型筛选、点击"预约"→ 校验会员卡（`validateCardForSchedule`）→ 跳转预约确认页。
7. 监听 `bookingSuccess` 事件，预约成功后刷新数据。

### 3.2 Loading

- `isLoadingCards` 控制会员卡区域 loading（既有）。
- 其余区域现状无独立 loading 态，本 Feature 不补（属 F3.4）。

### 3.3 Error

- **租户配置加载失败**（重点验证场景）：进入 `catch` → `console.warn` 并使用默认 90 分钟 → **不阻断后续数据加载，页面整体可用**。
- 排期/课程类型/预约/会员卡任一请求失败 → 各自 `catch` 处理（toast 或静默），页面不整页崩溃。
- 原崩溃点（570 行）位于 try 内，修复前该 ReferenceError 直接打断 `onMounted`，导致后续 `loadCourseTypes` / `loadSchedules` / `loadBookings` / `loadMembershipCards` **全部不执行**——这正是"页面加载即崩"的机理，也是修复后必须验证的恢复点。

### 3.4 空状态

- 当日无排期 → 排期列表渲染为空，无报错。
- 学员无会员卡 → 点击预约时既有校验逻辑给出「无法预约」提示，不崩溃。

### 3.5 Success

- 页面完整加载（日期/筛选/排期/会员卡区域均渲染）。
- 点击有卡的排期可正常跳转 `booking-confirm` 页。
- 租户配置生效（取消时限使用接口返回值而非默认值）。

### 3.6 Permission / Authentication

| 场景 | 预期行为 |
|------|---------|
| 未登录用户进入 | `checkLogin('student')` 拦截，跳转登录页 |
| 教师角色用户进入 | `checkLogin('student')` 拦截（角色不匹配） |
| Token 过期 | 请求层 401 refresh 链路统一处理 |

---

## 4. 通用流程约束（三页一致）

| 场景 | 预期行为 |
|------|---------|
| 页面加载（onMounted） | 无 ReferenceError，控制台无红色未捕获异常 |
| 页面快速切走（请求未返回即卸载） | `isUnmounted` 保护生效，不写入数据，无报错 |
| 弱网 / 请求超时 | 走各自 catch，toast 提示，不白屏卡死 |
| 接口返回非预期结构（空 data / 非数组） | `extractList` 兜底返回 `[]`，页面渲染空态不崩溃 |

## 5. 明确不覆盖的流程

- 预约确认页（`booking-confirm`）内部流程：本 Feature 只保证能"跳转到"该页。
- AI 助手（AiAssistant）相关流程。
- 四态视觉补全、类型检查清零：分别属 F3.4 / F3.2。
