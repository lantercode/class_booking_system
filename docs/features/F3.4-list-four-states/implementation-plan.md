# F3.4 — 列表页四态补全 · 实施方案

> Feature ID：F3.4
> 作者：frontend-engineer
> 日期：2026-09-29
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（纯前端 Feature，仅触达 `apps/admin-web`、`apps/student-web`、`apps/teacher-web`，不召后端 / DB / MCP）

---

## 1. Root Cause / 现状

三端列表页对四态（loading / empty / error / success）覆盖不一致：

1. **loading 态**：admin-web 全部用 `v-loading` 已覆盖；student/teacher 的 courses 页用 `el-skeleton` 已覆盖；但 student 的 schedule / my-bookings 与 teacher 的 students / schedule 虽有 `loading` 变量却**未在模板中渲染**（loading 形同摆设）。
2. **empty 态**：el-table 页依赖 Element Plus 内置默认空文案"暂无数据"（满足 AC"暂无数据提示"）；非 table 的卡片/日历列表多数已有 `el-empty`；但 teacher-web students 列表与 admin-web roles 角色列表**无任何空态**。
3. **error 态（最大缺口）**：全部 15 个列表页**无页面级 error 态**（`el-result` + 重试），仅 admin 多数页有 `ElMessage.error` toast；更严重的是 student-web schedule/my-bookings、teacher-web students/schedule 的主列表 fetch 与 admin schedules 的 lookup fetch 用 `catch (_) {}` / `catch {} /* ignore */` **静默吞错**，违反 `frontend/vue.md`："禁止把失败静默成成功"。
4. **success 态**：全部页面已具备，无需改动。

参考样板：`apps/admin-web/src/views/tenant/index.vue`（F3.3）已落地 `loadError` ref + `el-result icon="error"` + 重试按钮 + `v-loading` 的标准四态模式，本 Feature 在所有列表页复用该模式。

## 2. 页面 × 缺失态矩阵（事实核查结果，2026-09-29）

> 图例：✅ = 已具备；⚠️ = 部分具备 / 文案不当；❌ = 缺失；— = 不适用

### 2.1 admin-web（9 个列表页）

| # | 页面 | loading | empty | error | success |
|---|------|:---:|:---:|:---:|:---:|
| A1 | [courses/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/courses/index.vue) | ✅ v-loading×3（type/category/table） | ⚠️ type/category 面板 `el-empty description="--"`（文案不当）；主 table 用 el-table 内置空文案 | ❌ 仅 ElMessage.error，无 el-result/重试 | ✅ |
| A2 | [schedules/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/schedules/index.vue) | ✅ v-loading（table + 学员弹窗 table） | ⚠️ el-table 内置空文案（未显式配置） | ⚠️ fetchSchedules 有 ElMessage.error；**fetchLookups `catch (_) {}` 静默吞错** | ✅ |
| A3 | [users/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/users/index.vue) | ✅ v-loading | ⚠️ el-table 内置空文案 | ⚠️ fetchUsers 有 ElMessage.error；**fetchRoles `catch {} /* ignore */` 静默** | ✅ |
| A4 | [students/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/students/index.vue) | ✅ v-loading | ⚠️ el-table 内置空文案 | ❌ ElMessage.error，无 el-result/重试 | ✅ |
| A5 | [teachers/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/teachers/index.vue) | ✅ v-loading | ⚠️ el-table 内置空文案 | ❌ ElMessage.error，无 el-result/重试 | ✅ |
| A6 | [classrooms/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/classrooms/index.vue) | ✅ v-loading | ⚠️ `el-empty description="--"`（文案不当） | ❌ ElMessage.error，无 el-result/重试 | ✅ |
| A7 | [card-types/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/card-types/index.vue) | ✅ v-loading | ⚠️ el-table 内置空文案 | ❌ ElMessage.error，无 el-result/重试 | ✅ |
| A8 | [membership/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/membership/index.vue) | ✅ v-loading | ⚠️ el-table 内置空文案 | ⚠️ ElMessage.error 齐全但无页面级 el-result/重试 | ✅ |
| A9 | [roles/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/roles/index.vue) | ✅ v-loading（权限面板） | ⚠️ 权限面板有 hint el-empty；**角色列表无空态** | ❌ ElMessage.error，无 el-result/重试 | ✅ |

### 2.2 student-web（3 个列表页）

| # | 页面 | loading | empty | error | success |
|---|------|:---:|:---:|:---:|:---:|
| S1 | [courses/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/student-web/src/views/courses/index.vue) | ✅ `v-if=loading` + el-skeleton | ✅ `el-empty` 暂无课程 | ❌ `catch { courses.value = [] }` **静默吞错**，无 ElMessage.error / 无 el-result | ✅ |
| S2 | [schedule/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/student-web/src/views/schedule/index.vue) | ⚠️ 有 loading 变量但**模板未渲染** | ✅ `el-empty` 当天暂无排期 | ❌ fetchSchedules / fetchCourseName `catch (_) {}` **静默吞错** | ✅ |
| S3 | [my-bookings/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/student-web/src/views/my-bookings/index.vue) | ⚠️ 有 loading 变量但**模板未渲染** | ✅ `el-empty` 暂无预约记录 | ❌ fetchBookings `catch (_) {}` **静默吞错** | ✅ |

### 2.3 teacher-web（3 个列表页）

| # | 页面 | loading | empty | error | success |
|---|------|:---:|:---:|:---:|:---:|
| T1 | [courses/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/teacher-web/src/views/courses/index.vue) | ✅ `v-if=loading` + el-skeleton | ✅ `el-empty` 还没有课程 | ❌ `catch { courses.value = [] }` **静默吞错** | ✅ |
| T2 | [students/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/teacher-web/src/views/students/index.vue) | ⚠️ 有 loading 变量但**模板未渲染** | ❌ 列表为空时无任何提示 | ❌ fetchData `catch (_) {}` **静默吞错** | ✅ |
| T3 | [schedule/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/teacher-web/src/views/schedule/index.vue) | ⚠️ 有 loading 变量但**模板未渲染** | ✅ `el-empty` 当天暂无排期 | ⚠️ fetchCourses 有 ElMessage.error；fetchSchedules `catch (_) {}` **静默吞错** | ✅ |

**汇总**：15 个列表页，全部缺失页面级 error 态；6 个静默吞错（违反 vue.md）；5 个 loading 未在模板渲染；2 个无空态；多处 `description="--"` 空文案不当。

## 3. 修复策略（统一模式，复用 F3.3 tenant 样板）

### 3.1 error 态（核心，全部 15 页）

- 新增 `const loadError = ref('')`。
- 主列表 fetch：进入时 `loadError.value = ''`；catch 块 `loadError.value = e?.response?.data?.msg || '加载XX失败'` 并保留 `ElMessage.error(loadError.value)`（toast 即时反馈 + 页面级错误块双重展示）。
- 模板：在列表区域顶部插入 `<div v-if="loadError" class="list-error-block">` + `<el-result icon="error" :title="'加载XX失败'" :sub-title="loadError"><template #extra><el-button type="primary" @click="fetch">重试</el-button></template></el-result>`，原列表区域改为 `v-else`（或对卡片列表用 `v-else-if/v-else` 链）。
- 次级/lookup fetch（schedules 的 fetchLookups、users 的 fetchRoles、my-bookings 的 schedule/course 并行查询）：把 `catch (_) {}` / `catch {} /* ignore */` 改为 `ElMessage.error(...)`（不设页面级 error，因下拉空不影响主表，但必须可见反馈）。

### 3.2 loading 态（5 页）

- admin 全部已用 `v-loading`，不动。
- student courses / teacher courses 已用 el-skeleton，不动。
- student schedule / my-bookings、teacher students / schedule：给列表容器加 `v-loading="loading"`（最轻量，与 admin 一致），保留既有 el-skeleton 模式页不动。

### 3.3 empty 态（2 缺失 + 文案修正）

- teacher students：students-list 为空时加 `<el-empty description="暂无学员" :image-size="80" />`。
- admin roles：role-list 为空时加 `<el-empty description="暂无角色" :image-size="60" />`。
- el-table 页：依赖 el-table 内置"暂无数据"默认文案（满足 AC"暂无数据提示"），不强制加 `#empty` 以避免大改结构；统一为主表配置 `empty-text="暂无数据"` 使空态显式可控。
- 文案修正：classrooms `description="--"` → "暂无教室"；courses type/category 面板 `description="--"` → "暂无类型"/"暂无分类"。

### 3.4 success 态

- 全部已具备，零改动。

## 4. Affected Files（15 页 + 0 后端 + 0 新依赖）

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/admin-web/src/views/courses/index.vue` | +loadError +el-result/重试；type/category el-empty 文案；主表 empty-text |
| 2 | `apps/admin-web/src/views/schedules/index.vue` | +loadError +el-result/重试；fetchLookups 静默改 ElMessage.error；主表 empty-text |
| 3 | `apps/admin-web/src/views/users/index.vue` | +loadError +el-result/重试；fetchRoles 静默改 ElMessage.error；主表 empty-text |
| 4 | `apps/admin-web/src/views/students/index.vue` | +loadError +el-result/重试；主表 empty-text |
| 5 | `apps/admin-web/src/views/teachers/index.vue` | +loadError +el-result/重试；主表 empty-text |
| 6 | `apps/admin-web/src/views/classrooms/index.vue` | +loadError +el-result/重试；el-empty 文案"暂无教室" |
| 7 | `apps/admin-web/src/views/card-types/index.vue` | +loadError +el-result/重试；主表 empty-text |
| 8 | `apps/admin-web/src/views/membership/index.vue` | +loadError +el-result/重试；主表 empty-text |
| 9 | `apps/admin-web/src/views/roles/index.vue` | +loadError +el-result/重试；role-list +el-empty 空态 |
| 10 | `apps/student-web/src/views/courses/index.vue` | +loadError +el-result/重试；fetch catch 改 ElMessage.error |
| 11 | `apps/student-web/src/views/schedule/index.vue` | +loadError +el-result/重试；slots-section +v-loading；fetch 静默改 ElMessage.error |
| 12 | `apps/student-web/src/views/my-bookings/index.vue` | +loadError +el-result/重试；booking-list +v-loading；fetch 静默改 ElMessage.error |
| 13 | `apps/teacher-web/src/views/courses/index.vue` | +loadError +el-result/重试；fetch catch 改 ElMessage.error |
| 14 | `apps/teacher-web/src/views/students/index.vue` | +loadError +el-result/重试；students-list +v-loading +el-empty；fetch 静默改 ElMessage.error |
| 15 | `apps/teacher-web/src/views/schedule/index.vue` | +loadError +el-result/重试；schedule-list +v-loading；fetchSchedules 静默改 ElMessage.error |

**未触碰**：后端 `apps/api/**`、小程序 `apps/miniapp/**`、共享包 `packages/**`、登录/注册/dashboard/course-detail/profile 等非列表页；不新增依赖；不改 tsconfig；不改 API 契约。

## 5. 实施顺序

1. admin-web 9 页（同一模式批量应用）。
2. student-web 3 页。
3. teacher-web 3 页。
4. 三端分别 `npx vue-tsc --noEmit` 迭代至 0 error。
5. 三端分别 `pnpm run build` 验证。
6. 交付文档 + backlog 关闭。

## 6. 风险控制

- 统一模式、最小侵入：仅在列表区域加 `v-if/v-else` 切换与 `v-loading`，不改既有布局与样式。
- el-result/error 块仅用 Element Plus 既有组件，无新依赖。
- 静默 catch 改 ElMessage.error 属行为修正（符合 vue.md），不改变成功路径。
- 不改 baseURL（保持相对 `/api/v1`）、不本地重定义后端 DTO、不发明端点。
- 工作区边界：F3.1/F3.2/F3.3 已提交改动与本 Feature 改动在同文件时，只追加四态 hunk，不回滚既有逻辑。

## 7. 验证计划

- 静态：三端 `npx vue-tsc --noEmit` 0 error；grep 确认无残留 `catch (_) {}` 静默吞错（列表主 fetch 与 lookup fetch）。
- 构建：三端 `pnpm run build`（`vue-tsc -b && vite build`）成功。
- 回归：F3.3 tenant 页四态不受影响（本 Feature 不触碰 tenant/index.vue）。

## 8. UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | el-table 内置空文案是否满足 AC"el-empty 或暂无数据提示" | 满足：Element Plus el-table 默认 `empty-text` 为"暂无数据"。本 Feature 额外显式配置 `empty-text="暂无数据"` 使其可控可 grep，不强制加 `#empty` 槽以避免大改结构 |
| U2 | membership 页结构复杂（冻结/作废/批量），error 态是否覆盖全部子流程 | 本 Feature 只覆盖**主列表 fetch** 的页面级 error；写操作（冻结/作废）已有 ElMessage.error toast，不在 AC"列表页四态"范围 |
| U3 | student/teacher schedule 为日历 + 时段列表复合视图，error 态放哪 | 放在时段列表区域（slots-section / schedule-list），与 el-empty 同级；日历本身无独立 fetch，不需 error 态 |
