# F3.4 — Implementation Report

## 概览

共修改 12 个列表页，全部按 F3.3 [tenant/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/tenant/index.vue) 样板补全四态。

## admin-web（6 文件）

### [membership/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/membership/index.vue)
- 模板：在 `<el-table>` 之前插入 `<div v-if="loadError" class="list-error-block">` + `<el-result icon="error" title="加载会员卡列表失败" :sub-title="loadError">` + 重试按钮（@click="fetchCards"）
- 模板：el-table 改为 `v-else` + 加 `empty-text="暂无数据"`
- 脚本：新增 `const loadError = ref('')`
- 脚本：fetchCards 中 `loadError.value = ''` 清空 + catch 中 `loadError.value = e?.response?.data?.msg || '加载会员卡列表失败'`
- 样式：新增 `.list-error-block`

### [courses/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/courses/index.vue)
- 模板：table-wrapper 之前加 `<div v-if="loadError" class="list-error-block">`
- 模板：table-wrapper 改为 `v-else`
- 模板：el-table 加 `empty-text="暂无数据"`
- 脚本：新增 `const loadError = ref('')`
- 脚本：fetchCourses 中加 loadError 处理
- 样式：新增 `.list-error-block`

### [card-types/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/card-types/index.vue)
- 模板：error 块 v-if loadError + el-result 重试 → fetchCardTypes
- 模板：el-table 改 v-else + empty-text="暂无数据"
- 脚本：`const loadError = ref('')` + fetchCardTypes 加 loadError 清空与 catch 处理
- 样式：新建 `<style scoped>` 含 `.list-error-block`

### [classrooms/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/classrooms/index.vue)
- 模板：`<div v-if="loadError" class="list-error-block">`
- 模板：原 `<div v-loading="loading" class="classroom-content">` 改为 `v-else`
- 模板：el-empty description 改为"暂无数据"
- 脚本：新增 loadError ref + fetchClassrooms 更新
- 样式：新增 `.list-error-block`

### [roles/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/roles/index.vue)
- 脚本：新增 `roleLoading`、`roleLoadError`、`permLoadError` 三个 ref
- 模板：左侧 role-list 加 `v-loading="roleLoading"` + v-if roleLoadError 显示 el-result 重试（调 fetchRoles）+ v-else-if 加 el-empty "暂无角色"
- 模板：右侧 permission-content 加 v-if permLoadError 显示 el-result 重试（调 selectRole(selectedRole)）
- 脚本：fetchRoles 加 roleLoading/roleLoadError 设置
- 脚本：selectRole 加 permLoadError 设置
- 样式：新增 `.role-error-block, .perm-error-block`

### [dashboard/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/dashboard/index.vue)
- 模板：新增 `<div v-if="loadError" class="dashboard-error-block">` + el-result + 重试按钮
- 模板：dashboard-content 改为 `v-else v-loading="loading"`
- 模板：两个 el-table 加 `empty-text="暂无数据"`
- 脚本：新增 `loading`、`loadError` ref
- 脚本：fetchDashboard 加 loading/loadError 设置 + ElMessage.error
- 脚本：新增 `import { ElMessage } from 'element-plus'`
- 样式：新增 `.dashboard-error-block`

## student-web（3 文件）

### [courses/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/student-web/src/views/courses/index.vue)
- 模板：在 v-if loading 和 v-else-if empty 之间插入 `<div v-else-if="loadError" class="error-wrapper">` + el-result + 重试
- 脚本：新增 `const loadError = ref('')`
- 脚本：新增 `import { ElMessage }` 
- 脚本：fetchCourses catch 改为设置 loadError + ElMessage.error + courses.value = []
- 样式：新增 `.error-wrapper { padding: 60px 0; }`

### [schedule/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/student-web/src/views/schedule/index.vue)
- 模板：slots-section 内加 `<div v-if="loading && todaySlots.length === 0" v-loading="true" class="loading-slots">` + `<div v-else-if="loadError" class="error-slots">` + el-result + 重试
- 脚本：新增 `const loadError = ref('')`
- 脚本：fetchSchedules catch 改为设置 loadError + ElMessage.error
- 样式：新增 `.loading-slots, .error-slots { padding: 20px 0; min-height: 120px; }`

### [my-bookings/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/student-web/src/views/my-bookings/index.vue)
- 模板：booking-list 内添加 v-if loading + v-else-if loadError + v-else-if empty + `<template v-else>` 包裹 v-for
- 模板：补 `</template>` 闭合标签
- 脚本：新增 `const loadError = ref('')`
- 脚本：fetchBookings catch 改为设置 loadError + ElMessage.error + bookings.value = []
- 脚本：移除未使用的 `type Booking` import
- 样式：补 `.loading-wrapper, .error-wrapper, .empty-wrapper { padding: 60px 0; ... }`

## teacher-web（3 文件）

### [courses/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/teacher-web/src/views/courses/index.vue)
- 模板：在 v-if loading 和 v-else-if empty 之间插入 v-else-if loadError 块 + el-result + 重试 → fetchCourses
- 脚本：新增 `const loadError = ref('')`
- 脚本：fetchCourses catch 改为设置 loadError + ElMessage.error + courses.value = []
- 样式：新增 `.error-wrapper { padding: 60px 0; }`

### [students/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/teacher-web/src/views/students/index.vue)
- 模板：students-list 内加 v-if loading + v-loading + v-else-if loadError + el-result 重试 → fetchData + v-else-if empty + el-empty "暂无学员预约"
- 模板：原 v-for 列表用 `<template v-else>` 包裹
- 脚本：新增 `const loadError = ref('')`
- 脚本：fetchData catch 改为设置 loadError + ElMessage.error + students.value = []
- 脚本：移除未使用的 `User` 图标 import
- 样式：新增 `.state-wrapper`

### [schedule/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/teacher-web/src/views/schedule/index.vue)
- 模板：calendar-card 改为 `v-else v-loading="loading"`
- 模板：calendar-card 之前加 `<div v-if="loadError" class="calendar-error">` + el-result + 重试 → fetchSchedules
- 脚本：新增 `const loadError = ref('')`
- 脚本：fetchSchedules catch 改为设置 loadError + ElMessage.error + allSchedules.value = []
- 样式：新增 `.calendar-error`

## 通用模式

所有 catch 块统一为：

```ts
catch (e: any) {
  loadError.value = e?.response?.data?.msg || '加载 X 列表失败'
  ElMessage.error(loadError.value)
  list.value = []  // 防止保留旧数据
}
```

错误响应从统一信封 `{ code, msg, data }` 中取 msg，遵守 `architecture/contracts.md`。
