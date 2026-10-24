# F3.4 — Requirement

## Goal

所有列表页具备 loading / empty / error / success 四态，统一前端体验：

- loading：用 `v-loading` 指令（admin-web、teacher-web）或 `el-skeleton` / `v-loading` 区块（student-web、teacher-web）；
- empty：用 `el-empty` 或 `el-table empty-text="暂无数据"`，空态文案统一"暂无数据 / 还没有 / 暂无 X"；
- error：用 `el-result icon="error"` + 重试按钮，配合 `ElMessage.error(后端 msg)`；
- success：已有列表渲染即为 success 态，不改。

## Scope

修复三端缺失四态的列表页（共 12 个）：

### admin-web（6 个，本次新增）
- `apps/admin-web/src/views/membership/index.vue` — 缺 error 态
- `apps/admin-web/src/views/courses/index.vue` — 缺 error 态
- `apps/admin-web/src/views/card-types/index.vue` — 缺 error 态
- `apps/admin-web/src/views/classrooms/index.vue` — 缺 error 态
- `apps/admin-web/src/views/roles/index.vue` — 双面板缺 error 态
- `apps/admin-web/src/views/dashboard/index.vue` — 缺 error 态 + 缺 loading 视觉

### student-web（3 个）
- `apps/student-web/src/views/courses/index.vue` — 缺 error 态
- `apps/student-web/src/views/schedule/index.vue` — 缺 error 态
- `apps/student-web/src/views/my-bookings/index.vue` — 缺 loading 视觉 + empty 视觉 + error 态（catch 静默吞错）

### teacher-web（3 个）
- `apps/teacher-web/src/views/courses/index.vue` — 缺 error 态
- `apps/teacher-web/src/views/students/index.vue` — 缺 loading 视觉 + empty 视觉 + error 态
- `apps/teacher-web/src/views/schedule/index.vue` — 缺 loading 视觉 + error 态

## Out of Scope

- 不改后端、不改 API 调用方式、不改筛选/分页/排序逻辑、不改表单提交逻辑；
- 不引入新依赖（继续使用 Element Plus `v-loading` / `el-empty` / `el-result` / `ElMessage`）；
- 不改 miniapp（uni-app 端不在本 Feature 范围）；
- admin-web 已具备四态的页面（tenant / schedules / teachers / students / users）不动；
- admin-web 原有 unused function 警告（如 courses/index.vue 的 getCourseCountByType 等）属于既有技术债，不在本 Feature 范围。

## Backlog Reference

- `docs/delivery/feature-backlog.md` L247-255
