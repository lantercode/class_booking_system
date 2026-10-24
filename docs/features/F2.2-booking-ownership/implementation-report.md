# F2.2 — 预约数据归属与泄露修复 · 实施报告

> 日期：2026-09-28 ｜ 执行：backend-engineer
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

按 [implementation-plan.md](./implementation-plan.md) 完成预约数据归属与泄露修复：`GET /api/v1/bookings` 强制角色归属过滤；`GET /api/v1/bookings/{id}` 增加归属校验。归属校验全部落在 Service 层，Router 仅透传 `current_user`，OpenAPI 路径/方法/请求体/响应模型不变。三个子任务 T2.2.1 / T2.2.2 / T2.2.3 全部交付。

## 2. 变更明细

### 2.1 `apps/api/src/app/core/rbac/checker.py`（新增 1 个查询函数）

新增 `get_user_role_codes(db_session, user_id=None, tenant_id=None) -> set[str]`：

- 返回当前用户在指定租户下的角色 code 集合（含 `tenant_id IS NULL` 的全局角色，兼容 `super_admin`）。
- 复用 `check_roles` 既有 SQL 模式（`select(Role.code).join(UserRole).where(...)`），单次 JOIN 查询。
- 定位为"供 Service 层做基于角色的数据归属分流"，**非授权决策**；授权仍走 `check_permissions` / `check_roles`。
- `user_id` / `tenant_id` 缺失或查询异常时返回空集合（最小权限默认 → 调用方按 own 过滤）。

### 2.2 `apps/api/src/app/core/rbac/__init__.py`（导出）

- 增加 `from .checker import get_user_role_codes`。
- `__all__` 追加 `get_user_role_codes`，供 Service 层 `from app.core.rbac import get_user_role_codes` 导入。

### 2.3 `apps/api/src/app/modules/booking/repository.py`（`search` 加 `teacher_id`）

- `search` 签名新增 `teacher_id: int | None = None`。
- 统一 `needs_schedule_join = upcoming or teacher_id is not None` 判定，避免 `upcoming` 与 `teacher_id` 同时存在时重复 JOIN `CourseSchedule`。
- `teacher_id` 提供时在 base/count 两个 query 上 `where(CourseSchedule.teacher_id == teacher_id)`。
- 既有 `schedule_id` / `student_id` / `status` / `statuses` / `upcoming` / 分页逻辑原样保留。

### 2.4 `apps/api/src/app/modules/booking/service.py`（三处改动）

| 方法 | 改动 |
|------|------|
| `get_booking_by_id` | 新增 keyword-only 参数 `current_user: dict`。流程：`repo.get_by_id`（含租户过滤，跨租户 → None → 404 不泄露存在性）→ `_get_schedule_info_map` 取 `teacher_id` → `get_user_role_codes` 取角色集合 → admin 放行；否则 `owner OR teacher-of-schedule` 放行；其余 `PermissionException("无权查看该预约")`（403） |
| `list_bookings` | 新增 keyword-only 参数 `current_user: dict`。按 `is_admin = bool(role_codes & {"admin", "super_admin"})` 分流：admin 全量；student 强制 `student_id=user_id`；teacher 强制 `teacher_id=user_id`（按其排期）；无角色默认按 own（最小权限）。`schedule_id` 等既有筛选保留，与归属强制叠加生效 |
| `_get_schedule_info_map` | 返回 dict 补 `"teacher_id": row.teacher_id`，供 `get_booking_by_id` 复用做归属校验；`_to_response` 不消费该字段 → 零响应泄露 |

新增导入 `from app.core.rbac import get_user_role_codes`。

### 2.5 `apps/api/src/app/modules/booking/router.py`（两处透传）

- `list_bookings`：**删除** `student_id = current_user.get("user_id") if not schedule_id else None` 一行（违反"Router 不写业务判断"且逻辑错误——`schedule_id` 存在时把 `student_id` 置 None 导致越权）；改调 `booking_service.list_bookings(db, current_user=current_user, ...)`。
- `get_booking`：改调 `booking_service.get_booking_by_id(db, booking_id, current_user=current_user)`。
- 装饰器 `@require_permissions("booking:list")` / `@require_permissions("booking:read")` 原样保留；路径、方法、查询参数、请求体、响应模型均未动。

### 2.6 `apps/api/src/app/ai/mcp_server.py`（`get_my_bookings` 同步调用签名）

- `get_my_bookings` 工具原 `service.list_bookings(db, student_id=user_id, ...)` 改为 `service.list_bookings(db, current_user={"user_id": user_id, "tenant_id": tenant_id}, ...)`。
- student 用户行为不变（Service 强制 `student_id=user_id`）；teacher 用户行为由"空列表"改为"见自己排期下的预约"——符合 T2.2.3。`user_id`/`tenant_id` 由 AgentRuntime 从已认证 `get_current_user` 注入，不接受 LLM/前端传入。

### 2.7 `apps/api/tests/integration/test_booking_ownership.py`（新建）

session-scoped `booking_data` fixture 搭建 2 学员 / 2 教师 / 2 排期 / 3 预约（含种子学员 13900139001、种子教师 13800138001、新建学员 B、新建教师 T2），10 个用例覆盖 AC-1 ~ AC-6、AC-8、AC-10、AC-11（详见 [runtime-test-report.md](./runtime-test-report.md)）。

## 3. 实施中发现的问题

| # | 问题 | 处置 |
|---|------|------|
| 1 | 测试文件初次从 `app.modules.course.models` 导入 `CourseSchedule` / `ScheduleStatus`（实际位于 `app.modules.schedule.models`） | 改为 `from app.modules.schedule.models import CourseSchedule, ScheduleStatus`；`Course` 单独从 `app.modules.course.models` 导入 |
| 2 | 测试文件未使用导入 `hash_password` / `UserStatus`；`test_service_level_student_path_like_mcp` 多余 `client` 参数 | 删除未使用导入；用例改为只接受 `booking_data` fixture |
| 3 | fixture 原 function-scoped 每用例重建数据过重 | 重构为 session-scoped `booking_data`，所有用例共享一份搭建好的数据 |

## 4. 与计划的偏差

- 计划列出的 6 个文件（含测试）全部按方案交付，无新增计划外源文件改动。
- 实施中仅对测试文件做了 3 处工程性调整（见第 3 节），不涉及业务代码逻辑变更。

## 5. 数据兼容与迁移

- 无 DB 结构变更，无迁移。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。
- OpenAPI 路径/方法/查询参数/请求体/响应模型全部不变；`current_user` 是 `Depends(get_current_user)` 注入，不出现在 OpenAPI → 无需 `pnpm gen:types`，前端 4 端无影响。
