# F2.1 — 运行时测试报告

> 日期：2026-09-27
> 环境：本地开发机，FastAPI 测试服务器（127.0.0.1:8765，conftest 自动拉起），PostgreSQL（Docker 共享开发库，预置种子租户 dance-school），Redis 可用。

## 1. 测试入口

```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_admin_user_real.py -v
# 回归：
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest \
  tests/integration/test_auth_api.py tests/integration/test_rbac_enforcement.py -v
```

## 2. 结果摘要

| 套件 | 结果 |
|------|------|
| `test_admin_user_real.py` | **12 passed**（首轮 10 passed / 2 failed，修复后全绿） |
| `test_auth_api.py` + `test_rbac_enforcement.py`（回归） | **42 passed** |
| `test_user_api.py`（回归） | 5 passed / 1 failed —— 失败为**预先存在**缺陷，与本 Feature 无关（见第 5 节） |

## 3. 用例明细（test_admin_user_real.py，12/12 通过）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_create_user_real_and_alias` | AC-1/15 | 创建后 `id != 9999`；详情接口可查回相同手机号/昵称；`username`/`is_active` 别名正确；`tenant_id` 自动注入 |
| `test_create_user_duplicate_phone` | AC-2 | 重复手机号 → 400「手机号已被注册」 |
| `test_update_user_real` | AC-3 | PUT 改 `username`/`is_active=false` → 详情复核 `nickname` 变更、`status=0` |
| `test_delete_user_real` | AC-4 | DELETE 200；删除后 GET 详情 404（软删生效） |
| `test_delete_self_forbidden` | AC-5 | 删除自己 → 400「不能删除自己的账号」 |
| `test_list_users_real` | AC-6 | keyword 搜索命中种子管理员；列表无 Mock `user_N` 数据 |
| `test_assign_roles_real_and_cache_cleared` | AC-7/8 | admin 角色操作人分配 student 角色 → 详情 `roles` 含 student；预置的 `perms:{tenant}:{uid}` 缓存被清除 |
| `test_update_with_role_ids_clears_cache` | AC-17 | PUT 传 `role_ids` → 权限缓存被清除（经 UserService.assign_roles 链路） |
| `test_batch_delete_real` | AC-9 | 2 用户批量删除 → `deleted_count=2`，两者详情 404 |
| `test_batch_delete_atomic` | AC-10 | 批量含不存在 id（999999999）→ 404；**真实用户未被删除**（原子回滚验证） |
| `test_batch_delete_self_forbidden` | AC-11 | 批量含操作者自己 → 400；其他用户未被删除 |
| `test_public_stats_real` | AC-12 | 四项均为真实整数；`total_students>=1`、`total_teachers>=1`（种子），非硬编码 5000/200/1000/10000 |

## 4. 迭代记录

| 轮次 | 问题 | 修复 |
|------|------|------|
| 第 1 轮（10P/2F） | 测试代码 `redis.aclose()` 在当前 redis-py 版本不存在 | 改用 `close()` |
| 第 2 轮（10P/2F） | `UserService.assign_roles` 调用 `AuthRepository.get_role_by_id` 但该方法从未实现（休眠路径 AttributeError→500） | 在 `auth/repository.py` 补 `get_role_by_id`（计划外必要修复，已记入 implementation-report 2.4） |
| 第 3 轮 | — | **12/12 通过** |

## 5. 回归结论

- `test_auth_api.py`、`test_rbac_enforcement.py`：**42/42 通过**，RBAC 装饰器行为不变（student 访问 admin 端点仍 403 等）。
- `test_user_api.py::TestUserCRUD::test_create_user_success` 失败：`POST /api/v1/users` 返回 405。**已用 `git stash` 在 HEAD（不含本 Feature 任何改动）上复现同一失败** → 判定为预先存在缺陷（user 路由 POST 注册在 `/users/` 而 `redirect_slashes=False`，测试请求无尾斜杠），与本 Feature 无关。验证后已 `git stash pop` 完整恢复工作区。建议记入技术债务单独修复（不在 F2.1 范围）。

## 6. 性能与资源

- 12 用例全程约 5.5s；无慢查询告警；public/stats 为 4 条 count 查询。
