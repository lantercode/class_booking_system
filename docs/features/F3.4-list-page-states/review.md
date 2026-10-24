# F3.4 — Review

## Scope Review

- 纯前端 Feature，无后端、无 DB、无 MCP 改动；
- 改动 12 个列表页：
  - admin-web 6 个（membership / courses / card-types / classrooms / roles / dashboard）；
  - student-web 3 个（courses / schedule / my-bookings）；
  - teacher-web 3 个（courses / students / schedule）；
- 已具备四态的 5 个 admin 页面（tenant / schedules / teachers / students / users）未动；
- 未影响 miniapp；
- 未引入新依赖。

## Architecture Review

| 规则 | 结论 |
|------|------|
| 前端只能通过 HTTP API 访问后端 | ✅ 全部沿用既有 courseApi/bookingApi/scheduleApi 等 apiClient 调用 |
| 不在前端实现核心业务规则 | ✅ 仅补充四态 UI，不实现容量/冲突/扣次等业务规则 |
| 不在前端复制后端 DTO | ✅ 类型继续从 @dance-saas/api-client 引用 |
| 不新增第三套请求层 | ✅ 沿用 packages/api-client |
| 统一信封错误处理 | ✅ catch 走 e?.response?.data?.msg |
| 401 由 api-client 统一 refresh 重放 | ✅ 未在页面层另造刷新逻辑 |
| baseURL 相对路径 | ✅ 未改动 baseURL |

## Code Review

- catch 模式统一：`loadError.value = e?.response?.data?.msg || '加载 X 列表失败'` + `ElMessage.error(loadError.value)` + `list.value = []`；
- 模板四态顺序统一：v-if loading → v-else-if loadError → v-else-if empty → v-else success；
- admin-web el-table 风格：错误块在 el-table 之前 v-if loadError，el-table 改 v-else，empty 用 `empty-text="暂无数据"` 属性；
- student-web/teacher-web 卡片列表风格：用 `<template v-else>` 包裹 v-for，避免四态判断与 v-for 冲突；
- dashboard 统计页：dashboard-content 整体 v-loading + error 块在前；
- roles 双面板：左右两侧独立维护 loading/error；
- 不改业务逻辑：API 调用方式、筛选/分页/排序、表单提交均未改动。

## Regression Review

- 三端 vue-tsc 0 error，build 成功；
- 已有四态页面未改动，无回归风险；
- 前端 catch 中新增 `list.value = []` 是为了防止失败时保留旧数据，符合 UI 安全规范；
- 新增 import 仅限 ElMessage（dashboard 已有 stores/roles 已有，本次仅 dashboard 补 import）；其余页面 ElMessage 已 import。

## Acceptance Review

| AC 区段 | 状态 |
|---------|------|
| AC-1 ~ AC-6：admin-web 6 页 | ✅ 全部按计划落地 |
| AC-7 ~ AC-9：student-web 3 页 | ✅ 全部按计划落地 |
| AC-10 ~ AC-12：teacher-web 3 页 | ✅ 全部按计划落地 |
| AC-13：三端 vue-tsc 0 error | ✅ |
| AC-14：三端 build 成功 | ✅ |
| AC-15：grep 四态覆盖 | ✅ 16 个文件全部命中 |

## Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 三端实际运行时未联调（仅静态验证） | 中 | vue-tsc 0 error + build 成功保证编译/类型正确；401 refresh 由 api-client 统一处理 |
| dashboard/index.vue 多个 unused function 警告 | 低 | 属于既有技术债，不在本 Feature 范围（D-F3.4-1） |
| teacher-web/students state-wrapper 样式简化 | 低 | 仅满足 loading/error/empty 三态显示需求，不追求视觉精雕 |

## New Tech Debt

- D-F3.4-1：admin-web/courses/index.vue 等存在的 unused function 警告（getCourseCountByType / handlePageSizeChange / getCategoryTagType / getCourseThumbColor / getCourseThumbText）属于历史代码，本 Feature 仅补四态未清理，登记为独立技术债。
- D-F3.4-2：admin-web/dashboard 的 vue-tsc 警告中"unused var"类型若未来需要清理应单独 Feature 处理。

## Recommendation

**READY_FOR_ACCEPTANCE**

- Scope 完整覆盖（12 页面四态补全）；
- 架构合规（前端只走 HTTP API、不实现业务规则）；
- 静态验证通过（三端 vue-tsc 0 error + build 成功）；
- 回归无影响（已有四态页面未动）。
