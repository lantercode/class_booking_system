---
alwaysApply: false
globs: "apps/miniapp/**/*.vue,apps/miniapp/**/*.ts"
---

# 小程序规范（uni-app / 微信小程序）

适用：`apps/miniapp`（uni-app 3 + Vue 3 + TypeScript，目标平台 mp-weixin）。

## 平台约束

- 使用 uni-app API：`uni.request`、`uni.getStorageSync/setStorageSync`、`uni.navigateTo` 等；**禁止**使用浏览器 API（`localStorage`、`window`、`document`、DOM）和 axios。
- 页面注册在 `pages.json`，应用配置在 `manifest.json`；样式用 rpx + SCSS，滚动容器用 `scroll-view`，点击事件用 `@tap`。
- 本工程使用 **npm（非 pnpm）**；命令：`npm run dev:mp-weixin`、`npm run build:mp-weixin`，产物在微信开发者工具中验证。
- TypeScript `strict: true`，别名 `@/* → ./src/*`，不得放宽。

## 请求层（唯一）

- 只允许使用 `src/api/index.ts` 这一套请求封装（基于 `uni.request`，绝对 baseURL 取 `VITE_API_BASE_URL`）；全部 API 组（`authApi`、`bookingApi`、`aiChatApi` 等）集中在此文件，**禁止新建第二套请求客户端**。
- 登录态存储键：`token` / `refresh_token` / `tenant_slug`（uni storage）；401 刷新/重放/超时 abort 逻辑已在该文件实现，业务代码不得另写。
- 新增接口方法必须与后端路由逐一核对，禁止调用不存在的端点；信封 `{code,msg,data}` 与错误码处理与 Web 端语义保持一致（见 `architecture/contracts.md`）。

## 组件与状态

- 使用自研 `src/components/App*` 组件体系；Pinia 管理跨页状态。
- 学员/教师双角色通过不同目录（`pages/student`、`pages/teacher`）与角色 TabBar 区分，权限以后端为准，前端隐藏入口不等于鉴权。

## UI 与业务边界

- UI / 交互优化**不得擅自改动 API 调用、请求/响应数据结构或核心业务流程**；如需契约变更，走前后端协同修改。
- 核心业务规则以后端为唯一权威（见 `architecture/architecture.md`），前端校验仅为体验。
- AI 助手统一通过 `AiAssistant.vue` → `aiChatApi` → `POST /api/v1/ai/chat`；禁止直连 MCP，禁止在请求中传身份参数；预约/取消等写操作必须保留用户确认。
- 交付前必须通过 `npm run build:mp-weixin`，并在微信开发者工具做核心路径冒烟（登录、约课、取消、AI 对话）。

## 机密

- `WECHAT_SECRET` 等机密只存在于后端环境变量；小程序端不得包含任何密钥，`VITE_API_BASE_URL` 只放公开地址。
