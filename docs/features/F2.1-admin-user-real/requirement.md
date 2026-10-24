# F2.1 — admin 用户管理真实化 · 需求文档

> Feature ID：F2.1
> 作者：backend-engineer
> 日期：2026-09-27
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（纯后端任务，走 v2 轨道，不召前端）
> 依赖：F1.1（RBAC 生效）✅ 已完成

---

## Goal

admin 模块的用户管理端点（`/api/v1/admin/users*`）操作真实数据库，不再返回 Mock 数据。所有写操作通过复用既有 `UserService` 完成，遵守分层与事务规则。

## User Story

作为机构管理员（admin / super_admin），
我希望在管理后台创建、查看、更新、删除用户并分配角色时操作真实数据，
以便管理动作真实生效、权限变更即时反映到 RBAC 系统，
而不是收到伪造的成功响应。

## Background / 现状

`apps/api/src/app/modules/admin/service.py`（255 行）除 `get_my_permissions` 外全部为 Mock：

| 端点 | 现状 |
|------|------|
| `POST /admin/users` | 返回 id=9999 假数据，不落库 |
| `GET /admin/users` | 返回 100 条循环生成的假数据 |
| `GET /admin/users/{id}` | router 内联返回假数据 |
| `PUT /admin/users/{id}` | 返回拼接假数据 |
| `DELETE /admin/users/{id}` | 只清缓存，不真实删除 |
| `POST /admin/users/{id}/assign-roles` | 只清缓存，不真实分配 |
| `POST /admin/users/batch-delete` | 只清缓存，不真实删除 |
| `GET /admin/public/stats` | 硬编码 5000/200/1000/10000 |
| `GET /admin/dashboard` | 已是真实 SQL（router 层，保留不动） |
| `GET /admin/settings` | 硬编码租户配置（属 F3.3 范围，保留） |
| `GET /admin/my-permissions` | 已是真实实现（保留不动） |

可复用的真实能力已存在于 `app/modules/user/service.py` 的 `UserService`（create_user / update_user / delete_user / get_user_by_id / list_users / assign_roles），被 `/api/v1/users` 路由生产使用。

## Scope（In Scope）

1. `admin/service.py`：`create_user` / `update_user` / `delete_user` / `list_users` / `get_user`（新增）/ `assign_roles`（新增）/ `batch_delete_users`（新增）/ `get_public_stats`（新增）真实化，全部通过调用 `UserService` 或真实聚合查询实现。
2. `admin/router.py`：`GET /users/{user_id}`、`POST /users/{user_id}/assign-roles`、`POST /users/batch-delete`、`GET /public/stats` 改为调用 Service（移除 router 内联 Mock / 内联缓存清理逻辑）。
3. `user/service.py`：`delete_user` 增加 keyword-only 参数 `auto_commit: bool = True`（默认行为不变），供批量删除在同一事务中统一提交。
4. 新增集成测试 `tests/integration/test_admin_user_real.py`。

## Out of Scope

- `GET /admin/dashboard`：已是真实查询，保留现状（router 层直查 SQL 属历史分层债务，不在本 Feature 重构）。
- `GET /admin/settings`：硬编码租户配置，属 F3.3 范围。
- `GET /admin/my-permissions`：已是真实实现，不改。
- 前端（admin-web 等 4 端）：已 grep 确认前端**无任何页面消费** `/admin/users*` 端点（仅 `/admin/dashboard` 被消费且本就不变），本 Feature 不改 OpenAPI 路径/方法，无需前端改动。
- `packages/api-types` 重新生成：端点路径/方法/请求体 schema 均不变；响应体本来就是 `response_model=dict`（无 schema 约束），不产生契约漂移。
- 数据库结构变更：无（不新增/修改任何表与索引）。
- MCP / AI 层：不涉及。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1：`POST /admin/users` 创建的用户真实落库，可通过 `GET /admin/users/{id}` 与 DB 查询验证；重复手机号返回业务错误。
- AC-2：`PUT /admin/users/{id}` 的修改真实落库；`is_active=false` 映射为 `status=0`。
- AC-3：`DELETE /admin/users/{id}` 软删除生效（`deleted_at` 非空），删除后详情接口 404；不能删除自己（400）。
- AC-4：`GET /admin/users` 返回真实分页数据，`total` 与 DB 一致，keyword 搜索生效。
- AC-5：`POST /admin/users/{id}/assign-roles` 真实覆盖用户角色，分配后权限缓存被清除（`GET /admin/my-permissions` 或 RBAC checker 反映新权限）。
- AC-6：`POST /admin/users/batch-delete` 在同一事务中批量软删除；任一失败整体回滚；不能包含操作者自己。
- AC-7：`GET /admin/public/stats` 返回真实聚合数字（与 DB count 一致），保持公开（无需认证，但按中间件现状仍需租户头）。
- AC-8：回归 —— `test_auth_api`、`test_rbac_enforcement` 全量通过；RBAC 装饰器（user:create / user:read / user:update / user:delete / role:assign / super_admin）行为不变。
- AC-9：响应字段兼容 —— 保留 Mock 响应中的 `username`、`is_active` 字段（作为派生别名），同时返回真实字段，避免潜在外部消费者破窗。
- AC-10：无 Mock 残留 —— `admin/service.py` 与 `admin/router.py` 中不再存在硬编码假数据返回。
