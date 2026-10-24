# F3.3 — admin 租户设置页联调 · Requirement

## 背景

admin-web 的 `views/tenant/index.vue` 是纯硬编码 stub 页面（机构名="奕欣舞蹈"、电话="010-12345678" 等），无 API 调用、无保存逻辑。后端 tenant 模块只有 GET /settings 与 GET /info，无写端点。管理员无法通过管理后台修改租户配置（取消截止分钟数、可提前预约天数）与机构基本信息。

## Goal

- 后端补 `PUT /api/v1/tenant/settings` 与 `PUT /api/v1/tenant/info`；
- 前端 admin-web 租户设置页从 stub 改为真实联调：加载后端配置、保存修改；
- packages/api-client 补 tenant.ts，成为前端调用 tenant API 的唯一路径。

## Scope

- 后端：tenant/schemas.py（新建）、service.py（update 方法）、router.py（PUT 端点）；
- 前端：packages/api-client/src/tenant.ts（新建）、packages/api-client/src/index.ts（barrel）、apps/admin-web/src/views/tenant/index.vue（stub 改造）；
- 测试：tests/integration/test_tenant_update.py（后端 18 用例）；前端 vue-tsc + build 验证。

## Out of Scope

- DB schema 变更（settings JSONB 已存在）；
- tenant_middleware / ContextVar / ORM 租户事件链路（已有，不动）；
- student-web / teacher-web / miniapp（本 Feature 只涉及 admin-web）；
- 强类型 response_model 全项目迁移（登记为独立技术债）。
