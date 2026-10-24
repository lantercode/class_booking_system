# F3.3 — Release Note

## 概述

管理员可通过 admin-web「机构设置」页查看并修改租户配置（取消截止分钟数、可提前预约天数）与机构基本信息（名称、logo URL、联系电话、联系邮箱）。此前该页面为纯硬编码 stub。

## 新增 API

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| PUT | `/api/v1/tenant/settings` | admin, super_admin | 更新预约配置（浅合并） |
| PUT | `/api/v1/tenant/info` | admin, super_admin | 更新机构信息（部分更新） |

既有 GET /settings、GET /info 不变。

## 用户可见影响

- 管理员登录 admin-web → 机构设置 → 表单自动回填当前租户配置；
- 修改预约配置 → 保存 → 提示成功，配置即时生效（影响学员端取消/预约规则）；
- 修改机构信息 → 保存 → 提示成功；
- 无变更时保存 → 提示"没有需要保存的变更"，不调 API。

## 兼容性

- 纯新增端点（兼容变更），无破坏性变更；
- 无 DB schema 变更；
- 前端仅 admin-web 改动，其他三端无影响；
- 需重新 `pnpm gen:types` 以生成新增端点的 OpenAPI 类型（如已接入）。

## 验证

- 后端 18 个集成测试全部通过；
- 前端 vue-tsc 0 error + build 成功；
- test_rbac_enforcement 回归无影响。

## 部署注意

- 纯代码发布，无数据迁移；
- 依赖既有 RBAC 数据正确（admin 角色账号可调 PUT）。

## 后续事项

- D-F3.3-1：response_model 全项目统一迁移为强类型（独立技术债）。
