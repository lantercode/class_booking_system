# F3.4 — Acceptance Criteria

每个被改页面 × 每个态 = 1 条 AC，共 12 页面 × 缺失态条数。

## admin-web

### AC-1：membership/index.vue
- AC-1.1：el-table 加 `v-loading="loading"` 视觉加载态
- AC-1.2：el-table 加 `empty-text="暂无数据"` 空态
- AC-1.3：`v-if="loadError"` 显示 el-result icon="error" + 重试按钮
- AC-1.4：fetchCards catch 设置 `loadError.value = e?.response?.data?.msg || '加载会员卡列表失败'` 并 ElMessage.error
- AC-1.5：重试按钮点击 → 调用 fetchCards 重新加载

### AC-2：courses/index.vue
- AC-2.1：table-wrapper 改为 `v-else`，错误块 v-if loadError 在前
- AC-2.2：el-table 加 `empty-text="暂无数据"`
- AC-2.3：el-result icon="error" + 重试 → fetchCourses
- AC-2.4：catch 设置 loadError + ElMessage.error

### AC-3：card-types/index.vue
- AC-3.1：error 块 v-if loadError + el-result 重试 → fetchCardTypes
- AC-3.2：el-table 改为 v-else + `empty-text="暂无数据"`
- AC-3.3：新增 `<style scoped>` 含 `.list-error-block`
- AC-3.4：fetchCardTypes 加 loadError 清空 + catch 设置

### AC-4：classrooms/index.vue
- AC-4.1：error 块 v-if loadError + el-result 重试
- AC-4.2：`<div v-loading="loading" class="classroom-content">` 改为 `v-else`
- AC-4.3：el-empty description 改为"暂无数据"
- AC-4.4：fetchClassrooms 加 loadError 处理

### AC-5：roles/index.vue（双面板）
- AC-5.1：左侧 role-list 加 `v-loading="roleLoading"` + v-if roleLoadError 显示 el-result 重试（调 fetchRoles）
- AC-5.2：左侧 v-else-if 显示 el-empty "暂无角色"
- AC-5.3：右侧 permission-content 加 v-if permLoadError 显示 el-result 重试（调 selectRole(selectedRole)）
- AC-5.4：fetchRoles 加 roleLoading/roleLoadError 设置
- AC-5.5：selectRole 加 permLoadError 设置

### AC-6：dashboard/index.vue
- AC-6.1：error 块 v-if loadError + el-result 重试 → fetchDashboard
- AC-6.2：dashboard-content 改为 `v-else v-loading="loading"`
- AC-6.3：两个 el-table 加 `empty-text="暂无数据"`
- AC-6.4：新增 loading ref + loadError ref
- AC-6.5：fetchDashboard 加 loading/loadError 设置 + ElMessage.error
- AC-6.6：import { ElMessage } from 'element-plus'

## student-web

### AC-7：courses/index.vue
- AC-7.1：v-if loading 与 v-else-if empty 之间插入 v-else-if loadError 块 + el-result 重试 → fetchCourses
- AC-7.2：新增 loadError ref
- AC-7.3：fetchCourses catch 设置 loadError + ElMessage.error + courses.value = []

### AC-8：schedule/index.vue
- AC-8.1：slots-section 内加 v-if loading + v-loading="true" loading 区
- AC-8.2：加 v-else-if loadError + el-result 重试 → fetchSchedules
- AC-8.3：fetchSchedules catch 设置 loadError + ElMessage.error

### AC-9：my-bookings/index.vue
- AC-9.1：booking-list 内 v-if loading + v-loading="true" loading 区
- AC-9.2：v-else-if loadError + el-result 重试 → fetchBookings
- AC-9.3：v-else-if filteredBookings.length === 0 + el-empty "暂无预约记录"
- AC-9.4：原 v-for 列表用 `<template v-else>` 包裹
- AC-9.5：新增 loadError ref + ElMessage 已 import
- AC-9.6：fetchBookings catch 设置 loadError + ElMessage.error + bookings.value = []
- AC-9.7：补 `.loading-wrapper, .error-wrapper` 样式
- AC-9.8：移除未使用的 `type Booking` import

## teacher-web

### AC-10：courses/index.vue
- AC-10.1：v-if loading 后插入 v-else-if loadError + el-result 重试 → fetchCourses
- AC-10.2：新增 loadError ref
- AC-10.3：fetchCourses catch 改为设置 loadError + ElMessage.error + courses.value = []
- AC-10.4：补 `.error-wrapper` 样式

### AC-11：students/index.vue
- AC-11.1：students-list 内加 v-if loading + v-loading="true" loading 区
- AC-11.2：v-else-if loadError + el-result 重试 → fetchData
- AC-11.3：v-else-if students.length === 0 + el-empty "暂无学员预约"
- AC-11.4：原 v-for 列表用 `<template v-else>` 包裹
- AC-11.5：新增 loadError ref
- AC-11.6：fetchData catch 设置 loadError + ElMessage.error + students.value = []
- AC-11.7：移除未使用的 `User` 图标 import
- AC-11.8：补 `.state-wrapper` 样式

### AC-12：schedule/index.vue
- AC-12.1：calendar-card 改为 `v-else v-loading="loading"`
- AC-12.2：calendar-card 之前加 v-if loadError 错误块 + el-result 重试 → fetchSchedules
- AC-12.3：新增 loadError ref
- AC-12.4：fetchSchedules catch 改为设置 loadError + ElMessage.error + allSchedules.value = []
- AC-12.5：补 `.calendar-error` 样式

## 验证 AC

### AC-13：三端类型检查 0 error
- `cd apps/admin-web && npx vue-tsc --noEmit` → 0 error
- `cd apps/student-web && npx vue-tsc --noEmit` → 0 error
- `cd apps/teacher-web && npx vue-tsc --noEmit` → 0 error

### AC-14：三端 build 成功
- `cd apps/admin-web && pnpm run build` → ✓ built in 3.54s
- `cd apps/student-web && pnpm run build` → ✓ built in 3.08s
- `cd apps/teacher-web && pnpm run build` → ✓ built in 3.52s

### AC-15：grep 四态覆盖证据
- 16 个被改页面（含 F3.3 tenant）全部具备 `v-loading|el-skeleton` + `el-empty|empty-text` + `el-result icon="error"|loadError`
