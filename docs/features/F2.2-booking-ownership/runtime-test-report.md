# F2.2 — 运行时测试报告

> 日期：2026-09-28
> 环境：本地开发机，FastAPI 测试服务器（127.0.0.1:8765，conftest 自动拉起），PostgreSQL（Docker 共享开发库，预置种子租户 dance-school），Redis 可用。

## 1. 测试入口

```bash
# 主测试
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_ownership.py -v

# 回归（AC-7）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest \
  tests/integration/test_auth_api.py \
  tests/integration/test_rbac_enforcement.py \
  tests/integration/test_admin_user_real.py -v
```

## 2. 结果摘要

| 套件 | 结果 |
|------|------|
| `test_booking_ownership.py` | **10 passed**（首轮即全绿，4.47s） |
| `test_auth_api.py`（回归） | **25 passed** |
| `test_rbac_enforcement.py`（回归） | **17 passed** |
| `test_admin_user_real.py`（回归） | **12 passed** |
| **合计** | **64 passed, 4 warnings in 15.64s** |

warnings 均为既有第三方库 deprecation（passlib `crypt`、uvicorn/websockets legacy、FastAPI `example`），与本 Feature 无关。

## 3. 用例明细（test_booking_ownership.py，10/10 通过）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_student_list_only_own` | AC-3 | 学员 A 调 `GET /bookings` → items 的 `student_id` 全部 == A 的 user_id（不含 B 的预约） |
| `test_student_query_by_schedule_only_own` | AC-1 | 学员 A 在 schedule_T 创建预约；学员 B 调 `GET /bookings?schedule_id=schedule_T` → items 不含 A 的预约；A 自己调则命中 |
| `test_student_get_others_booking_forbidden` | AC-2 | 学员 A 调 `GET /bookings/{B 的预约 id}` → 403，msg 含"无权查看" |
| `test_student_get_own_booking_ok` | AC-10 | 学员 A 调 `GET /bookings/{A 自己的预约 id}` → 200 |
| `test_get_nonexistent_returns_404` | AC-11 | 学员 A 调 `GET /bookings/999999999` → 404，msg 含"不存在" |
| `test_teacher_list_only_own_schedules` | AC-4 | 教师 T 名下 schedule_T 有学员预约；非 T 排期 schedule_T2 也有预约；T 调 `GET /bookings` → items 的 `schedule_id` 全部 ∈ {schedule_T}（不含 schedule_T2） |
| `test_teacher_get_own_schedule_booking_ok` | AC-5（正） | 教师 T 调 `GET /bookings/{其排期下的预约 id}` → 200 |
| `test_teacher_get_other_schedule_booking_forbidden` | AC-5（负） | 教师 T 调 `GET /bookings/{他人排期下的预约 id}` → 403 |
| `test_admin_full_access` | AC-6 | super_admin 调 `GET /bookings` 与 `GET /bookings/{任意 id}` → 200；items 含跨学员数据 |
| `test_service_level_student_path_like_mcp` | AC-8 | 直调 `BookingService.list_bookings(db, current_user={"user_id":<student A>, "tenant_id":...})` → 仅返回 A 自己的预约（模拟 MCP `get_my_bookings` 的 student 路径） |

## 4. 用例明细（回归套件）

### `test_auth_api.py`（25/25 通过）

- `TestRegister`（4）：注册成功 / 重复手机号 / 手机号格式 / 弱密码
- `TestLogin`（3）：登录成功 / 密码错 / 用户不存在
- `TestGetMe`（3）：带 token / 无 token（401）/ 无效 token（401）
- `TestRefreshToken`（3）：刷新成功 / 已用过的 refresh / 无效 refresh
- `TestLogout`（2）：登出成功 / 缺 refresh
- `TestCompleteAuthFlow`（1）：完整 happy path
- `TestEdgeCases`（3）：缺字段 / 多余字段被忽略 / SQL 注入防护
- `TestAccessTokenBlacklist`（6）：登出黑名单 access token / 无 refresh 仍黑名单 / 其他用户 token 不受影响 / 黑名单 token 命中 optional 端点 / 登出后重登 / 重复登出 401

### `test_rbac_enforcement.py`（17/17 通过）

- `TestPermissionEnforcement`（4）：student 不能创建用户 / student 不能访问 admin users / admin 写端点过 RBAC / 未认证 401
- `TestRoleBoundaries`（7）：student 过 booking 角色检查 / teacher 不能创建预约 / student 不能访问 teacher me / student 不能访问 tenant settings / admin 可访问 tenant settings / admin 可访问 admin settings / student 不能访问 admin settings
- `TestDebugEndpointsRemoved`（4）：test-token / test-exception / test-auth 端点已移除 / health 仍公开
- `TestAiIntentsProtected`（2）：intents 需认证 / intents 带 token 可访问

### `test_admin_user_real.py`（12/12 通过）

- 12 个 admin 用户管理真实化用例（F2.1 交付，全部回归通过）。

## 5. 迭代记录

| 轮次 | 问题 | 修复 |
|------|------|------|
| 第 1 轮 | 测试文件从 `app.modules.course.models` 导入 `CourseSchedule` → ImportError | 改为 `from app.modules.schedule.models import CourseSchedule, ScheduleStatus`；`Course` 单独从 `app.modules.course.models` 导入 |
| 第 1 轮 | 测试文件未使用导入 `hash_password` / `UserStatus`；`test_service_level_student_path_like_mcp` 多余 `client` 参数 | 删除未使用导入；用例改为只接受 `booking_data` fixture |
| 第 1 轮 | fixture function-scoped 每用例重建数据过重 | 重构为 session-scoped `booking_data`，所有用例共享一份搭建好的数据 |
| 第 2 轮 | — | **10/10 通过**（首轮修复后即全绿） |

## 6. 回归结论

- `test_auth_api.py`（25/25）、`test_rbac_enforcement.py`（17/17）、`test_admin_user_real.py`（12/12）全部通过 → **AC-7 满足**。
- 认证 / RBAC / admin 用户管理行为未受本 Feature 影响：JWT 双 token、黑名单、角色边界、admin 用户管理全量回归通过。
- 本 Feature 改动的 `core/rbac/checker.py` 新增 `get_user_role_codes` 不影响既有 `check_permissions` / `check_roles` 装饰器行为（既有授权链路零变更）。

## 7. 性能与资源

- 10 个 booking ownership 用例约 4.47s（含 fixture 一次性搭建 2 学员 / 2 教师 / 2 排期 / 3 预约）。
- `get_user_role_codes` 单次 JOIN 查询；list 接口本身已有 student_map / schedule_map 批量查询，归属查询占比低。
- 全部 64 用例 15.64s，无慢查询告警。
