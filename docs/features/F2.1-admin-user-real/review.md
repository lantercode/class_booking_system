# F2.1 — Review

> 日期：2026-09-27 ｜ 审查人：backend-engineer（自审 + 规则清单）

## Scope

- 变更严格限于 Feature 定义：`admin/service.py`、`admin/router.py`、`user/service.py`（+1 参数）、`auth/repository.py`（+1 缺失方法，实施中由测试发现的必要修复）、新增测试。
- `dashboard`/`settings`/`my-permissions` 未动，符合 Out of Scope 约定。
- 未引入新依赖、未改 DB 结构、未改 OpenAPI 路径/方法。

## Architecture

- Router → Service → Repository 分层合规；admin 跨模块复用 `UserService`，未直写其 Repository。
- `batch_delete_users` 通过 `auto_commit=False` 复用 `UserService.delete_user` 全部校验（删自己/教师排课/软删），在同一 `AsyncSession` 统一提交 —— 满足"统一提交"且无业务逻辑重复。
- public/stats 为 Service 内 count 聚合，与 `UserService` 既有 `db.execute(select(...))` 模式一致；显式租户过滤弥补 count 查询不触发 ORM 自动注入的盲区。

## Code

- 全部 Mock 清除（grep 验证）；保留 `get_my_permissions` 真实实现。
- 兼容别名 `username`/`is_active` 由 `_to_admin_dict` 统一派生，避免散点拼接。
- `BusinessException`(500) → `ValidationException`(400) 修正了"不能删除自己"的错误语义。
- 顺带修复 router `update_user` 缺 `db` 实参的历史 bug。

## Security

- 所有受保护端点 RBAC 装饰器原样保留；assign-roles 维持双重校验（`require_roles` + `require_permissions("role:assign")`），且 UserService 内部第三重校验操作人角色。
- 高危操作日志（删除/批量删除）保留且不泄露敏感信息；错误经统一异常体系返回信封，无 traceback。
- 租户隔离三层机制未被绕过；未扩大中间件跳过白名单。

## Transaction / Concurrency

- 单写操作由 UserService 内部提交（沿用既有事务边界）。
- 批量删除原子性由测试 `test_batch_delete_atomic` 实证（部分失败 → 全部回滚）。
- 权限缓存失效覆盖：assign_roles（Service 内）、delete（Service 内）、batch_delete（提交后统一清）、update 传 role_ids（经 Service 内 assign_roles）。

## Regression

- `test_auth_api` + `test_rbac_enforcement`：42/42 通过。
- `test_user_api` 1 失败经 `git stash` 对照实验证实为预先存在缺陷（尾斜杠问题），与本变更无关。

## Acceptance

- AC-1 ~ AC-12、AC-15、AC-17：12 个集成测试全部通过。
- AC-13/14（回归）：通过。
- AC-16（无 Mock 残留）：grep 验证通过。

## 遗留事项（不阻塞）

1. `test_user_api.py::test_create_user_success` 预先存在的 405（`/users` vs `/users/` 尾斜杠）——建议单开债务项修复（统一路由或改测试）。
2. `GET /admin/dashboard` 的 SQL 仍在 Router 层（历史债务，真实但分层不合规）——留待后续重构。
3. `AuthRepository.get_role_by_id` 不带租户过滤，理论上可跨租户引用角色 ID（操作已被 admin/super_admin 权限门禁）——建议后续在 assign_roles 增加角色租户归属校验。

## 结论

**READY_FOR_ACCEPTANCE**
