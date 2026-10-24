# F1.1 — RBAC 权限校验真实生效 · 运行时测试报告

> Feature ID：F1.1
> 日期：2026-09-27
> 环境：macOS / Python 3.12.13 / pytest 9.0.3 / 真实 uvicorn（8765）+ 真实 Redis + 测试库种子数据

---

## 1. 新增集成测试：test_rbac_enforcement.py

命令：

```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_rbac_enforcement.py -v
```

结果：**17 passed in 3.00s**

### 逐 AC 映射

| AC | 用例 | 结果 |
|----|------|------|
| AC-2.1 学员创建用户 403 | test_student_cannot_create_user | PASS |
| AC-2.2/3.1 学员访问 admin/users 403 | test_student_cannot_access_admin_users | PASS |
| AC-2.3 admin 写端点不被 RBAC 拦截 | test_admin_write_endpoint_passes_rbac | PASS |
| AC-2.4 无 token 401 | test_unauthenticated_request_returns_401 | PASS |
| AC-4.1 学员通过 booking 角色校验 | test_student_passes_booking_role_check | PASS |
| AC-4.9 教师创建预约 403 | test_teacher_cannot_create_booking | PASS |
| AC-4.8 学员访问 teachers/me 403 | test_student_cannot_access_teacher_me | PASS |
| AC-4.7 学员访问 tenant/settings 403 | test_student_cannot_access_tenant_settings | PASS |
| AC-4.11 admin 访问 tenant/settings | test_admin_can_access_tenant_settings | PASS |
| AC-4.10 admin 访问 admin/settings 200 | test_admin_can_access_admin_settings | PASS |
| AC-3.2 学员访问 admin/settings 403 | test_student_cannot_access_admin_settings | PASS |
| AC-5.1 test-token 404 | test_test_token_endpoint_removed | PASS |
| AC-5.2 test-exception 404 | test_test_exception_endpoint_removed | PASS |
| AC-5.3 test-auth 404 | test_test_auth_endpoint_removed | PASS |
| AC-5.4 health 公开 200 | test_health_endpoint_still_public | PASS |
| AC-6.1 intents 无 token 401 | test_intents_requires_authentication | PASS |
| AC-6.2 intents 有 token 非 401 | test_intents_accessible_with_token | PASS |

AC-1.x / AC-4.2~4.5 / AC-5.5 / AC-7.x 为代码审查类，见 static-verification.md。

## 2. 回归测试

### 2.1 test_auth_api.py（单独运行）

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_auth_api.py -v
```

结果：**25 passed in 4.86s**（含 F1.2 黑名单 6 用例，确认与 RBAC 变更无交互回归）。

### 2.2 test_rbac_real_redis.py + test_agent_runtime.py

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_rbac_real_redis.py tests/test_agent_runtime.py
```

结果：**11 passed in 0.21s**。

### 2.3 已知预存失败（与 F1.1 无关，不修）

- `tests/integration/test_tenant_isolation.py`：3 个预存失败。
- `tests/test_mcp_server.py`：4 个预存失败。
- 多文件并行运行时 `test_auth_api.py` 出现 httpx.ConnectError（live_server 8765 端口竞争的测试基础设施问题）；单独运行 25/25 通过，确认**非 F1.1 回归**。该并行冲突建议后续由测试基础设施 Feature 处理。

## 3. 测试过程中修复的环境问题（dev 库数据污染）

| 问题 | 现象 | 处置 |
|------|------|------|
| teacher/student 种子用户被软删 | 登录 401"该手机号未注册" | SQL 恢复 status/deleted_at |
| user 2 角色被污染为 student | teacher 调 booking 未 403（假阳性的反面） | SQL 更正 role_id=3 |
| student 角色被错误授予 user:create | 学员创建用户未 403 | SQL 删除该 role_permission |

以上均为 dev 库历史污染，非本次代码改动引入；CI/测试库由 conftest 全新种子不受影响。

## 4. 结论

AC-2/3/4（运行时部分）/5/6 全部 PASS；AC-8.1/8.2/8.3 回归通过；AC-8.5 预存失败未扩大。运行时验证通过。
