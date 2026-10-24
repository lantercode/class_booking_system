---
alwaysApply: false
globs: "apps/admin-web/**/*.vue,apps/admin-web/**/*.ts,apps/student-web/**/*.vue,apps/student-web/**/*.ts,apps/teacher-web/**/*.vue,apps/teacher-web/**/*.ts,packages/api-client/**/*.ts,packages/api-types/**/*.ts"
---

# Web 前端规范（Vue3 三端 + 共享包）

适用：`apps/admin-web`、`apps/student-web`、`apps/teacher-web`、`packages/api-client`、`packages/api-types`。
小程序（`apps/miniapp`）见 `frontend/mini-program.md`。

## 技术栈与写法（统一三端）

- Vue 3.4 + `<script setup lang="ts">` + Composition API；TypeScript `strict: true`（tsconfig 已开启，不得放宽）；路径别名 `@/* → src/*`。
- 状态管理用 Pinia **setup store 风格**：`defineStore('name', () => { const x = ref(); return { x } })`。
- UI 库统一 Element Plus 2.7 + `@element-plus/icons-vue`；不得引入第二套重型 UI 库，不得把小程序的 `App*` 组件搬到 Web。
- 构建三端一致：`vue-tsc -b && vite build`；提交前必须类型检查 + 构建通过。

## API 集成

- 所有请求走 `@dance-saas/api-client`：`apiClient.get/post/...` 或具名 API 对象（如 `bookingApi`）。
- baseURL 固定相对路径 `/api/v1`，**禁止硬编码绝对 URL**；禁止在业务代码里新建 axios 实例。
- 鉴权头、`x-tenant-slug` 头、401 刷新重放由 api-client 拦截器统一处理，业务代码不得重复实现（见 `architecture/contracts.md`）。
- 新增 API 对象方法必须与后端真实路由逐一核对（方法、路径、参数、响应），禁止声明不存在的端点；集合路径不加尾斜杠。
- 类型只从 api-client 导出 / `api-types` 引用，禁止本地重新声明后端 DTO，禁止手改生成文件。

## 业务边界

- 前端不实现核心业务规则（容量、权限、课时、状态机），前端校验只做即时反馈；以后端校验为最终结果。
- 错误处理必须区分 HTTP 401（已自动处理）/403/409/500，并展示后端 `msg`；禁止把失败静默成成功。

## 页面完整性

- 数据视图必须覆盖四态：loading / empty / error / success。
- 写操作（预约、取消、会员卡操作）要有确认与失败提示。
- 各端 `src/mock/` 仅用于开发期联调前占位；正式页面入口不得长期引用 mock，联调完成后移除引用。
