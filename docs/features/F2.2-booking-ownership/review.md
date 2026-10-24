# F2.2 — Review

> 日期：2026-09-28 ｜ 审查人：backend-engineer（自审 + 规则清单）

## Scope

- 变更严格限于 Feature 定义：`core/rbac/checker.py`（+1 查询函数）、`core/rbac/__init__.py`（导出）、`booking/repository.py`（+1 参数）、`booking/service.py`（三处归属校验）、`booking/router.py`（两处透传）、`ai/mcp_server.py`（同步 `get_my_bookings` 调用）、新增测试。
- `create_booking` / `cancel_booking` / `cancel_booking_by_schedule` / `check_in` / `complete` 等**写操作端点未动**，符合 Out of Scope 约定。
- 未引入新依赖、未改 DB 结构、未改 OpenAPI 路径/方法/请求体/响应模型。

## Architecture

- Router → Service → Repository 分层合规：`list_bookings` / `get_booking` Router 仅提取参数 + 透传 `current_user` + 调 Service + 返回响应；删除了原 Router 层 `student_id = current_user.get("user_id") if not schedule_id else None` 的业务判断（双重违规：在 Router 写 if/else + 逻辑错误导致越权）。
- Service 层承载全部归属规则：`get_user_role_codes` 取角色集合 → admin 全量 / student 强制 own / teacher 强制其排期 / 无角色默认 own。
- MCP `get_my_bookings` → `BookingService.list_bookings`（不直查 Repository），满足 AI 边界（`ai/mcp.md` / `ai/ai-architecture.md`）。
- `core/rbac/checker.py` 是核心基础设施（非业务模块 Repository），`get_user_role_codes` 与既有 `check_roles` 同源、同 SQL 模式，不构成跨模块 Repository 越界。

## Code

- `get_user_role_codes` 复用 `check_roles` 既有 SQL 模式（`select(Role.code).join(UserRole).where(...)`），单次查询返回集合；非授权决策（授权仍走 `check_permissions` / `check_roles`）。
- `list_bookings` 角色优先级 admin > student > teacher > 默认（own），语义清晰、最小惊讶；最小权限默认避免"无角色 → 全量"的越权回归。
- `get_booking_by_id` owner OR teacher-of-schedule OR admin 三选一放行；不存在的 `booking_id` → 404（不泄露存在性）；跨租户由 `TenantAwareRepository` 自动过滤为 None → 404。
- `_get_schedule_info_map` 返回值补 `teacher_id` 字段零额外查询（该函数已 SELECT `CourseSchedule.teacher_id`）、零响应泄露（`_to_response` 不消费）。
- Router 删除 `student_id` 推导，遵守"Router 不写业务判断"；身份透传与既有 `cancel_booking` 一致。

## Security

- 受保护端点装饰器 `@require_permissions("booking:list")` / `@require_permissions("booking:read")` 原样保留；新增的 `get_user_role_codes` 非授权决策，不替代 `check_permissions` / `check_roles`，授权边界不动。
- `current_user` 由 `Depends(get_current_user)` 注入；MCP 身份来自 AgentRuntime 受信上下文，不接受 LLM/前端传入的 `user_id` / `tenant_id`（满足 `ai/ai-architecture.md` 身份可信链路）。
- 租户隔离三层机制未被绕过：`BookingRepository` 继承 `TenantAwareRepository`；`get_by_id` 跨租户返回 None → 404；`get_user_role_codes` 用 `or_(Role.tenant_id == tid, Role.tenant_id.is_(None))` 兼容全局角色。
- 不泄露存在性：跨租户 / 不存在的 `booking_id` 一律 404（非 403）；无权访问的同类资源 403（msg "无权查看该预约"，不含内部细节）。
- 未扩大中间件跳过白名单；无硬编码密钥；日志不输出敏感信息。

## Transaction / Concurrency

- 本 Feature 为只读端点（`GET /bookings` / `GET /bookings/{id}`），无写操作事务边界变更。
- `get_user_role_codes` 单次只读查询，无并发写风险；异常时返回空集合（最小权限默认）。

## Regression

- `test_auth_api.py`（25/25）+ `test_rbac_enforcement.py`（17/17）+ `test_admin_user_real.py`（12/12）：**54/54 通过** → AC-7 满足。
- 认证 / RBAC / admin 用户管理行为未受影响：JWT 双 token、黑名单、角色边界、admin 用户管理全量回归通过。

## Acceptance

- AC-1 ~ AC-6、AC-8、AC-10、AC-11：10 个集成测试全部通过（详见 [runtime-test-report.md](./runtime-test-report.md)）。
- AC-7（回归）：通过（54/54）。
- AC-9（分层合规）：静态 grep 验证 router 无角色判断分支；Service 调 `get_user_role_codes`；MCP 不直写跨模块 Repository（详见 [static-verification.md](./static-verification.md)）。
- AC-12（跨租户不可见）：既有 `TenantAwareRepository` 行为，跨租户 `booking_id` → 404（非 403，不泄露存在性）。

## 遗留事项（不阻塞）

1. `booking/router.py` 仍有 3 处 `student_id = current_user.get("user_id")`（L36 `create_booking` / L150 `cancel_booking` / L174 `cancel_booking_by_schedule`）——均为写操作端点，`@require_roles("student")` 已限定只有学员能调，`student_id` 是 actor 自身身份而非越权过滤。F2.2 Scope 仅含 `GET` 端点，这些写操作不在本 Feature 范围。建议后续单开债务项审查写操作端点的归属校验是否完备（`cancel_booking` Service 内部已有 `student_id` 校验，`create_booking` / `cancel_booking_by_schedule` 需复核）。
2. `get_user_role_codes` 每次请求单次 DB 查询——若后续 list 接口 QPS 上升，可考虑加角色集合缓存（key 如 `roles:{tenant_id}:{user_id}`，TTL 与权限缓存 300s 对齐）。当前性能占比低，不阻塞。
3. 教师同时持有 student 角色时按 D3 优先级 student 赢（U2）——生产中教师不应同时持有 student 角色；如确有此场景，后续可加显式"切换视角"参数（不在本 Feature 范围）。

## 结论

**READY_FOR_ACCEPTANCE**
