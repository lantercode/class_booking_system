# F2.2 — 预约数据归属与泄露修复 · 需求文档

> Feature ID：F2.2
> 作者：backend-engineer
> 日期：2026-09-28
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（纯后端任务，走 v2 轨道，不召前端）
> 依赖：F1.1（RBAC 生效）✅ 已完成；F2.1（admin 真实化）✅ 已完成

---

## Goal

预约查询端点（`GET /api/v1/bookings`、`GET /api/v1/bookings/{id}`）按角色强制数据归属，杜绝学员越权查看他人预约、杜绝任意认证用户凭 ID 查任意预约的越权读。归属校验在 Service 层完成，Router 仅负责把已认证身份透传给 Service。

## User Story

作为学员 A，
我希望无论怎样拼接查询参数（包括传 `schedule_id`）都只能看到自己的预约，
也无法通过 `GET /bookings/{id}` 查看学员 B 的预约详情，
以便我的预约隐私不被同租户其他学员窥探。

作为教师，
我希望能看到排在我名下排期的所有预约（含其他学员），以便点名/签到/跟课。

作为管理员，
我希望保留全量查询能力（按 `schedule_id`/`status` 等过滤），以便处理客诉与排课调整。

## Background / 现状（已核查的代码事实）

| 事实 | 证据 |
|------|------|
| `list_bookings` 越权 | [router.py:67](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/router.py#L67)：`student_id = current_user.get("user_id") if not schedule_id else None`。学员传 `schedule_id` 时 → `student_id=None` → 返回该排期下全租户所有预约 |
| `get_booking_by_id` 无归属校验 | [service.py:321-331](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L321-331)：取到 booking 后直接返回，任意认证用户凭任意 `booking_id` 可查任意预约 |
| `CourseSchedule.teacher_id` 字段存在 | [schedule/models.py:33](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/models.py#L33)：`teacher_id: Mapped[int]`（FK users.id） |
| `BookingRepository.search` 支持 `schedule_id`/`student_id` | [repository.py:22](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L22)：已有这两个过滤参数，需补 `teacher_id` |
| **JWT payload 不含 roles** | [auth/service.py:168-173](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/auth/service.py#L168-173)：`token_data = {"user_id", "tenant_id"}`，无 `roles`/`role_id`。`current_user` 仅为 payload，**不能** 直接读角色 |
| 角色查询已有实现 | [auth/repository.py:102](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/auth/repository.py#L102)：`AuthRepository.get_user_roles(session, user_id) -> list[Role]`；[user/service.py:837](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/user/service.py#L837)：`UserService.get_user_roles` 包装之；[rbac/checker.py:335-399](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/rbac/checker.py#L335-399)：`check_roles` 内已有 Role.code 集合查询模式 |
| MCP 也调用 list_bookings | [ai/mcp_server.py:201](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/ai/mcp_server.py#L201)：`get_my_bookings` 工具调 `service.list_bookings(db, student_id=user_id, ...)`，user_id/tenant_id 由 AgentRuntime 从已认证上下文注入（受信） |
| `BookingRepository.get_by_id` 已有租户过滤 | 继承 `TenantAwareRepository`，ORM 事件自动注入 `tenant_id` |
| `_get_schedule_info_map` 已 SELECT teacher_id | [service.py:421](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L421)：查询含 `CourseSchedule.teacher_id`，但返回 dict 未包含 → 需补 `teacher_id` 字段以支持归属校验 |

## Scope（In Scope）

1. `booking/service.py`：
   - `list_bookings` 新增 `current_user: dict` 参数，按角色分流（student 强制 `student_id=user_id`；teacher 按 `teacher_id=user_id` 过滤其排期；admin/super_admin 全量）。
   - `get_booking_by_id` 新增 `current_user: dict` 参数，做归属校验（owner / teacher-of-schedule / admin 三者之一放行，否则 403）。
   - `_get_schedule_info_map` 返回值补 `teacher_id` 字段（供归属校验复用，不外泄到响应——`_to_response` 未消费该字段）。
2. `booking/router.py`：
   - `list_bookings` 删除 router 层的 `student_id` 推导；改为透传 `current_user` 给 Service。
   - `get_booking` 透传 `current_user` 给 Service。
3. `booking/repository.py`：`search` 新增 `teacher_id: int | None` 参数，提供时 JOIN `CourseSchedule` 并按 `teacher_id` 过滤。
4. `core/rbac/checker.py`：新增 `get_user_role_codes(db_session, user_id, tenant_id) -> set[str]`，复用 `check_roles` 既有查询模式，供 Service 一次性取得角色集合。
5. `ai/mcp_server.py`：`get_my_bookings` 工具改为透传 `current_user={"user_id":..., "tenant_id":...}`，删除显式 `student_id=user_id`（改由 Service 按角色分流；student 用户行为不变，teacher 用户改为见自己排期下的预约——符合 T2.2.3）。
6. 新增集成测试 `tests/integration/test_booking_ownership.py`。

## Out of Scope

- `check_in`/`complete` 端点的归属校验（F2.3 负责）。
- `cancel_booking`/`cancel_booking_by_schedule`：已存在 `student_id` 校验（[service.py:175](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L175)），不在本 Feature 范围。
- 前端 4 端（admin-web / student-web / teacher-web / miniapp）：契约（路径/方法/查询参数/响应模型）不变，仅行为更安全；已 grep 确认前端调用方按现有契约使用，无需改动。
- `packages/api-types` 重新生成：无 OpenAPI 变更。
- 数据库结构变更：无（不新增/修改表与索引）。
- 在 JWT payload 里塞 roles：不在本 Feature 范围（会扩大到 auth 模块 + 密钥刷新策略，应单独立项；本 Feature 用 DB 查询角色，单次查询、走既有 RBAC 基础设施）。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1：学员 A 调 `GET /bookings?schedule_id=<B 的排期>` 只返回 A 自己在该排期的预约（不含 B 的）。
- AC-2：学员 A 调 `GET /bookings/{B 的预约 id}` → 403。
- AC-3：学员 A 调 `GET /bookings`（不带 schedule_id）只返回 A 自己的预约。
- AC-4：教师调 `GET /bookings` 只返回排在其名下排期的预约。
- AC-5：教师调 `GET /bookings/{其排期下的预约 id}` → 200；调他人排期的预约 → 403。
- AC-6：admin/super_admin 调 `GET /bookings` 与 `GET /bookings/{id}` 全量可查。
- AC-7：回归 `test_auth_api`、`test_rbac_enforcement`、`test_admin_user_real` 全量通过。
- AC-8：MCP `get_my_bookings`（student 用户）行为不变，仍返回自己预约。
- AC-9：分层合规——Router 不写角色判断；Service 调 RBAC 核心取角色；不直写跨模块 Repository。
