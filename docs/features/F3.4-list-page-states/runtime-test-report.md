# F3.4 — Runtime Test Report

## 环境

- 前端：Node.js / vue-tsc 2.2.0 / vite 5.2.8 / Element Plus 2.7+
- 后端：本 Feature 纯前端改动，无运行时后端依赖

## 类型检查

| 端 | 命令 | 结果 |
|----|------|------|
| admin-web | `npx vue-tsc --noEmit` | 0 error（无输出） |
| student-web | `npx vue-tsc --noEmit` | 0 error（无输出） |
| teacher-web | `npx vue-tsc --noEmit` | 0 error（无输出） |

## 构建

| 端 | 命令 | 结果 |
|----|------|------|
| admin-web | `pnpm run build` | ✓ built in 3.54s |
| student-web | `pnpm run build` | ✓ built in 3.08s |
| teacher-web | `pnpm run build` | ✓ built in 3.52s |

构建产物正常输出到 `dist/`，仅有 chunks > 500kB 的既有警告（非本 Feature 引入）。

## 四态覆盖验证

### loading 态

- 三端 16 个列表页全部具备 `v-loading` 或 `el-skeleton` 视觉加载态；
- 关键页面：
  - [admin/dashboard](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/dashboard/index.vue)：dashboard-content 整体 v-loading
  - [teacher/schedule](file:///Users/lixiang/Desktop/class_booking_system/apps/teacher-web/src/views/schedule/index.vue)：calendar-card 整体 v-loading
  - [student/my-bookings](file:///Users/lixiang/Desktop/class_booking_system/apps/student-web/src/views/my-bookings/index.vue)：v-if loading + v-loading

### empty 态

- 16 个列表页全部具备 `el-empty` 或 `el-table empty-text="暂无数据"`；
- admin-web el-table 用 `empty-text` 属性；
- student-web/teacher-web 用 `el-empty` 组件。

### error 态

- 16 个列表页全部具备 `<el-result icon="error">` + 重试按钮；
- catch 块统一从 `e?.response?.data?.msg` 取后端错误信息（统一信封 `{code, msg, data}`）；
- 同步调用 `ElMessage.error(loadError.value)` 显示顶部 toast。

### success 态

- 各页面原有列表渲染逻辑保留，未做改动。

## 用户场景验证

### 场景 1：首次进入 → loading → success

模拟：在 [student/courses/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/student-web/src/views/courses/index.vue) 初始 onMounted 触发 fetchCourses，loading=true 显示 loading-wrapper，接口成功后进入 success 态。

### 场景 2：进入空列表 → loading → empty

模拟：[teacher/students/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/teacher-web/src/views/students/index.vue) 中 students.length === 0 → v-else-if empty → el-empty "暂无学员预约"。

### 场景 3：接口失败 → loading → error → 重试 → success

模拟：在 [teacher/schedule/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/teacher-web/src/views/schedule/index.vue) fetchSchedules 抛错 → loadError 设置 → ElMessage.error toast + 显示 el-result + 重试按钮 → 用户点击重试重新调 fetchSchedules。

### 场景 4：双面板（admin/roles）

[admin/roles/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/roles/index.vue) 左侧 role-list 与右侧 permission-content 独立维护 loading/error，单边失败不影响另一边。

### 场景 5：Dashboard（admin/dashboard）

[admin/dashboard/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/dashboard/index.vue) 整个 dashboard-content v-loading + 失败显示 el-result + 重试 fetchDashboard；成功后两个 el-table 各自 empty-text="暂无数据"。

## 回归影响

- 后端：无（纯前端 Feature）；
- miniapp：无（不在本 Feature 范围）；
- 已有四态页面（admin/tenant、admin/schedules、admin/teachers、admin/students、admin/users）：未改动；
- 前端业务逻辑（API 调用、筛选、分页、排序、表单提交）：未改动。

## 汇总判定

- 三端 vue-tsc 0 error
- 三端 build 成功
- 16 个被改列表页四态覆盖完整
- 无新依赖、无后端改动
- catch 走统一信封 msg，遵守 `architecture/contracts.md`

**结论：PASS，READY_FOR_ACCEPTANCE。**
