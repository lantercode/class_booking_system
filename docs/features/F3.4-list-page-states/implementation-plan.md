# F3.4 — Implementation Plan

## 页面清单 × 缺什么态 × 修复策略

### admin-web（6 页）

| 页面 | 已有 | 缺 | 修复策略 |
|------|------|----|----------|
| membership/index.vue | loading、empty、success | error | el-table 改 v-else，加 error 块 v-if loadError + el-result 重试 → fetchCards；catch 加 loadError 设置 + ElMessage.error；补 .list-error-block 样式 |
| courses/index.vue | loading、empty、success | error | table-wrapper 改 v-else，error 块在前；el-table 加 empty-text="暂无数据"；fetchCourses catch 加 loadError 处理 |
| card-types/index.vue | loading、empty、success | error | error 块 + el-table 改 v-else + empty-text；新建 style scoped；fetchCardTypes 加 loadError 清空 + catch 处理 |
| classrooms/index.vue | loading、success | error、empty 描述优化 | error 块 v-if loadError；原 v-loading 改为 v-else；el-empty description 改"暂无数据"；fetchClassrooms 更新 |
| roles/index.vue | success | loading、empty、error（双面板） | roleLoading + roleLoadError + permLoadError 三 ref；左 role-list v-loading + v-if error + v-else-if empty；右 permission-content v-if error；fetchRoles/selectRole 加处理 |
| dashboard/index.vue | success | loading、empty、error | dashboard-content 改 v-else v-loading；error 块 v-if loadError；两个 el-table 加 empty-text；fetchDashboard 加 loading/loadError + ElMessage.error；补 ElMessage import |

### student-web（3 页）

| 页面 | 已有 | 缺 | 修复策略 |
|------|------|----|----------|
| courses/index.vue | loading、empty、success | error | 在 v-if loading 与 v-else-if empty 之间插入 v-else-if loadError + el-result 重试；新增 loadError ref；fetchCourses catch 改为设置 loadError + ElMessage.error + courses.value = []；补 .error-wrapper 样式 |
| schedule/index.vue | success、empty | loading、error | slots-section 内加 v-if loading + v-loading loading 区；加 v-else-if loadError + el-result 重试；fetchSchedules catch 改为设置 loadError + ElMessage.error；补 .loading-slots, .error-slots 样式 |
| my-bookings/index.vue | success | loading、empty、error | booking-list 内 v-if loading + v-else-if loadError + v-else-if empty + `<template v-else>` 包裹 v-for；新增 loadError ref；fetchBookings catch 改为设置 loadError + ElMessage.error + bookings.value = []；补 .loading-wrapper, .error-wrapper 样式；移除未用的 Booking type import |

### teacher-web（3 页）

| 页面 | 已有 | 缺 | 修复策略 |
|------|------|----|----------|
| courses/index.vue | loading、empty、success | error | 在 v-if loading 与 v-else-if empty 之间插入 v-else-if loadError + el-result 重试；新增 loadError ref；fetchCourses catch 改为设置 loadError + ElMessage.error + courses.value = []；补 .error-wrapper 样式 |
| students/index.vue | success | loading、empty、error | students-list 内 v-if loading + v-loading + v-else-if loadError + v-else-if empty + `<template v-else>` 包裹 v-for；新增 loadError ref；fetchData catch 改为设置 loadError + ElMessage.error + students.value = []；移除未用的 User 图标 import；补 .state-wrapper 样式 |
| schedule/index.vue | success、empty | loading、error | calendar-card 改 v-else v-loading；前加 v-if loadError 错误块 + el-result 重试；新增 loadError ref；fetchSchedules catch 改为设置 loadError + ElMessage.error + allSchedules.value = []；补 .calendar-error 样式 |

## 通用修复模板

```ts
// 1. 新增 ref
const loadError = ref('')

// 2. fetchXxx 头部清空
async function fetchXxx() {
  loading.value = true
  loadError.value = ''
  try {
    // ...
  } catch (e: any) {
    loadError.value = e?.response?.data?.msg || '加载 X 列表失败'
    ElMessage.error(loadError.value)
    list.value = []  // 防止保留旧数据
  } finally {
    loading.value = false
  }
}
```

```html
<!-- 3. 模板四态分布 -->
<!-- loading -->
<div v-if="loading" v-loading="true" class="loading-wrapper">
  <div style="height: 80px"></div>
</div>
<!-- error -->
<div v-else-if="loadError" class="error-wrapper">
  <el-result icon="error" title="加载 X 列表失败" :sub-title="loadError">
    <template #extra>
      <el-button type="primary" @click="fetchXxx">重试</el-button>
    </template>
  </el-result>
</div>
<!-- empty -->
<div v-else-if="list.length === 0" class="empty-wrapper">
  <el-empty description="暂无数据" />
</div>
<!-- success -->
<template v-else>
  <div v-for="item in list" :key="item.id">...</div>
</template>
```

## 风险控制

- admin-web el-table 风格：错误块在 el-table 之前 v-if loadError，el-table 改 v-else；
- student-web/teacher-web 卡片列表风格：用四态 if/else 链；
- dashboard 统计页：dashboard-content 整体 v-loading；
- roles 双面板：左右两侧独立维护 loading/error；
- 不改业务逻辑：catch 中只补充 loadError 设置 + ElMessage 提示，不改动请求方式与数据处理逻辑。
