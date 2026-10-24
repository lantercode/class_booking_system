# F2.1 — admin 用户管理真实化 · 验收标准

> 每条 AC 均可通过集成测试（`tests/integration/test_admin_user_real.py`）或静态检查验证。
> 测试入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_admin_user_real.py -v`

| # | AC | 验证方式 | 预期 |
|---|----|---------|------|
| AC-1 | 创建用户真实落库 | IT：`POST /admin/users` 后 `GET /admin/users/{id}` 返回相同手机号；响应 `id != 9999` | 201；DB 可查；角色分配生效 |
| AC-2 | 重复手机号拒绝 | IT：用已存在手机号再次创建 | 400，msg 含"手机号已被注册" |
| AC-3 | 更新真实生效 | IT：创建后 `PUT` 改 nickname/is_active，再 `GET` 核对 | 200；`nickname` 变更、`status==0`（is_active=false） |
| AC-4 | 删除真实生效（软删） | IT：创建后 `DELETE`，再 `GET` 详情 | DELETE 200；GET 404 |
| AC-5 | 不能删除自己 | IT：admin 删除自己的 id | 400，msg 含"不能删除自己" |
| AC-6 | 列表真实分页 | IT：`GET /admin/users?keyword=<种子手机号>` | `total>=1`，items 含真实种子用户（13800000001 等），非 `user_N` 假数据 |
| AC-7 | assign-roles 真实生效 | IT：对新建用户分配 student 角色 → `GET /users/{id}/roles`（或 admin 详情）核对角色 | 200；角色列表包含 student |
| AC-8 | assign-roles 清权限缓存 | IT：分配角色后，目标用户权限缓存 key `perms:{tenant}:{user}` 被删除 | Redis 中无该 key |
| AC-9 | batch-delete 真实生效 | IT：创建 2 个用户 → batch-delete → 分别 GET 详情 | 均 404；响应 `deleted_count==2` |
| AC-10 | batch-delete 原子性 | IT：batch-delete 包含一个不存在 id + 一个真实 id | 请求失败（4xx）；真实 id 未被删除（GET 仍 200） |
| AC-11 | batch-delete 拒绝删自己 | IT：user_ids 含操作者 id | 400，无任何删除 |
| AC-12 | public/stats 真实聚合 | IT：`GET /admin/public/stats`（带租户头） | 返回整数且 `total_students>=1`、`total_teachers>=1`（种子含 1 学员 1 教师），不再是 5000/200/1000/10000 |
| AC-13 | RBAC 不变 | 回归：`test_rbac_enforcement.py` 全量 | 全部通过（student 访问 /admin/users 仍 403） |
| AC-14 | 认证回归 | 回归：`test_auth_api.py` 全量 | 全部通过 |
| AC-15 | 响应兼容别名 | IT：创建/详情/列表响应包含 `username` 与 `is_active` 字段 | 存在且与 `nickname`/`status` 派生一致 |
| AC-16 | 无 Mock 残留 | 静态：grep `9999`、`user_{i}`、`5000` 等于 admin 模块 | 无匹配 |
| AC-17 | 权限缓存失效（更新角色） | IT：`PUT` 传 role_ids 后目标用户缓存 key 被清 | Redis 中无该 key |
