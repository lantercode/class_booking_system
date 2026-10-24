# F2.2 — 预约数据归属与泄露修复 · 实施方案

> Feature ID：F2.2
> 作者：backend-engineer
> 日期：2026-09-28
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

两个端点的归属校验缺失或被错误逻辑绕过：

1. **`list_bookings` 越权**：[router.py:67](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/router.py#L67) 用 `student_id = current_user.get("user_id") if not schedule_id else None` 推导。一旦学员传 `schedule_id`，`student_id` 被置 None → 返回该排期下全租户所有学员预约。这是"在 Router 用 if/else 做业务判断"且逻辑错误的双重违规。
2. **`get_booking_by_id` 无归属校验**：[service.py:321-331](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L321-331) 取到 booking 直接返回。任意认证用户凭任意 `booking_id` 可查任意同租户预约。

**身份来源事实**：`current_user`（JWT payload）仅含 `user_id` + `tenant_id`（[auth/service.py:168-173](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/auth/service.py#L168-173)），**不含 `roles`/`role_id`**。因此角色不能从 payload 读，必须由 Service 经 RBAC 核心查 DB 取得。

## 已核查的代码事实（Evidence）

| 事实 | 证据 |
|------|------|
| `current_user` 不含 roles | `auth/service.py` 全部 `create_access_token` 调用（L173/232/378/429/534）的 `token_data` 仅 `{user_id, tenant_id}` |
| `BookingRepository.search` 现有过滤 | `repository.py:22-84`：支持 `schedule_id`/`student_id`/`status`/`statuses`/`upcoming`；`upcoming` 时 JOIN `CourseSchedule` |
| `_get_schedule_info_map` 已 SELECT teacher_id | `service.py:421` 查询列含 `CourseSchedule.teacher_id`，但返回 dict（L441-448）未包含 → 加一行即可复用做归属校验 |
| `_to_response` 不消费 teacher_id | `service.py:451-509`：仅读 `course_name`/`start_at`/`end_at`/`classroom_name`/`teacher_name` → dict 补 `teacher_id` 不会泄露到响应 |
| RBAC 已有角色集合查询模式 | `core/rbac/checker.py:370-383`：`check_roles` 内 `select(Role.code).join(UserRole).where(...)` 返回集合 |
| `ScheduleRepository.get_by_id` 已被 booking service 使用 | `service.py:62`（create_booking）、`service.py:224`（_do_cancel_booking）——既有跨模块 Repository 直用（历史债务，本 Feature 不扩大但沿用） |
| MCP `get_my_bookings` 调 list_bookings | `ai/mcp_server.py:201`：`service.list_bookings(db, student_id=user_id, ...)`；user_id/tenant_id 受信 |
| 角色优先级（admin > student > teacher） | 见 Decision D3：admin 放行；非 admin 时 student 强制 own；非 admin 非 student 时 teacher 按其排期 |
| 既有 tenant 隔离 | `BookingRepository` 继承 `TenantAwareRepository`；`get_by_id`/`search` 均带 `tenant_id` 过滤 |

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/core/rbac/checker.py` | 新增 `get_user_role_codes(db_session, user_id, tenant_id) -> set[str]`，复用 `check_roles` 既有查询模式 |
| 2 | `apps/api/src/app/modules/booking/repository.py` | `search` 新增 `teacher_id: int \| None` 参数；提供时 JOIN `CourseSchedule` 并按 `teacher_id` 过滤；统一 `needs_schedule_join` 判定避免重复 JOIN |
| 3 | `apps/api/src/app/modules/booking/service.py` | `list_bookings` / `get_booking_by_id` 新增 `current_user` 参数并按角色做归属校验；`_get_schedule_info_map` 返回值补 `teacher_id` |
| 4 | `apps/api/src/app/modules/booking/router.py` | `list_bookings` 删除 router 层 `student_id` 推导，透传 `current_user`；`get_booking` 透传 `current_user` |
| 5 | `apps/api/src/app/ai/mcp_server.py` | `get_my_bookings` 工具透传 `current_user={"user_id","tenant_id"}`，删除显式 `student_id=user_id` |
| 6 | `apps/api/tests/integration/test_booking_ownership.py` | 新建，覆盖 AC-1 ~ AC-12 |

## Exact Fix（要点）

### 1. `core/rbac/checker.py`：新增 `get_user_role_codes`

```python
async def get_user_role_codes(
    db_session: AsyncSession,
    user_id: int | None = None,
    tenant_id: int | None = None,
) -> set[str]:
    """返回当前用户在指定租户下的角色 code 集合（含全局角色）。

    供 Service 层做基于角色的数据归属分流（非授权决策；授权仍走 check_permissions/check_roles）。
    单次查询，复用 check_roles 的查询模式。
    """
    _user_id = user_id or get_user_id()
    _tenant_id = tenant_id or get_tenant_id()
    if not _user_id or not _tenant_id:
        return set()
    try:
        stmt = (
            select(Role.code)
            .join(UserRole)
            .where(
                and_(
                    UserRole.user_id == _user_id,
                    or_(Role.tenant_id == _tenant_id, Role.tenant_id.is_(None)),
                )
            )
        )
        result = await db_session.execute(stmt)
        return {row[0] for row in result.fetchall()}
    except Exception as e:
        logger.error(f"[RBAC Checker] 角色查询失败: {type(e).__name__}: {e}")
        return set()
```

### 2. `booking/repository.py`：`search` 加 `teacher_id`

```python
async def search(self, db, *, schedule_id=None, student_id=None, teacher_id=None,
                 status=None, statuses=None, upcoming=False, page=1, page_size=20):
    base_query = select(Booking)
    count_query = select(func.count()).select_from(Booking)

    needs_schedule_join = upcoming or teacher_id is not None
    if needs_schedule_join:
        base_query = base_query.join(CourseSchedule, Booking.schedule_id == CourseSchedule.id)
        count_query = count_query.join(CourseSchedule, Booking.schedule_id == CourseSchedule.id)
    # ...既有 schedule_id/student_id/statuses/upcoming 过滤...
    if teacher_id:
        base_query = base_query.where(CourseSchedule.teacher_id == teacher_id)
        count_query = count_query.where(CourseSchedule.teacher_id == teacher_id)
    # ...
```

### 3. `booking/service.py`：归属校验

```python
async def list_bookings(self, db, *, current_user, schedule_id=None, ...):
    user_id = current_user.get("user_id")
    tenant_id = current_user.get("tenant_id")
    role_codes = await get_user_role_codes(db, user_id, tenant_id)
    is_admin = bool(role_codes & {"admin", "super_admin"})

    forced_student_id = None
    forced_teacher_id = None
    if not is_admin:
        if "student" in role_codes:           # student 优先于 teacher
            forced_student_id = user_id
        elif "teacher" in role_codes:
            forced_teacher_id = user_id
        else:
            # 无 admin/student/teacher 角色 → 仅能看自己作为学员的预约（最小权限默认）
            forced_student_id = user_id

    items, total = await self.repo.search(
        db, schedule_id=schedule_id, student_id=forced_student_id,
        teacher_id=forced_teacher_id, status=status, statuses=statuses,
        upcoming=upcoming, page=page, page_size=page_size,
    )
    # ...既有 student_map/schedule_map/响应构建不变...

async def get_booking_by_id(self, db, booking_id, *, current_user):
    booking = await self.repo.get_by_id(db, booking_id)
    if not booking:
        raise NotFoundException("预约不存在")
    schedule_map = await self._get_schedule_info_map(db, [booking.schedule_id])
    schedule_info = schedule_map.get(booking.schedule_id) or {}

    user_id = current_user.get("user_id")
    tenant_id = current_user.get("tenant_id")
    role_codes = await get_user_role_codes(db, user_id, tenant_id)
    is_admin = bool(role_codes & {"admin", "super_admin"})
    if not is_admin:
        is_owner = booking.student_id == user_id
        is_teacher_of_schedule = (
            "teacher" in role_codes and schedule_info.get("teacher_id") == user_id
        )
        if not is_owner and not is_teacher_of_schedule:
            raise PermissionException("无权查看该预约")
    return self._to_response(booking, schedule_info=schedule_info)
```

`_get_schedule_info_map` 返回 dict 补 `"teacher_id": row.teacher_id`。

### 4. `booking/router.py`：透传 current_user

```python
# list_bookings：删除 student_id 推导
result = await booking_service.list_bookings(
    db, current_user=current_user, schedule_id=schedule_id, statuses=statuses,
    display_status=display_status, upcoming=is_upcoming,
    exclude_cancelled=exclude_cancelled, page=page, page_size=page_size,
)
# get_booking
result = await booking_service.get_booking_by_id(db, booking_id, current_user=current_user)
```

### 5. `ai/mcp_server.py`：透传 current_user

```python
result = await service.list_bookings(
    db,
    current_user={"user_id": user_id, "tenant_id": tenant_id},
    status=status_int, upcoming=upcoming,
    exclude_cancelled=True if upcoming else None,
    page=1, page_size=20,
)
```

## 关键决策记录（Decision）

| # | 决策 | 理由 |
|---|------|------|
| D1 | 角色由 Service 经 `app.core.rbac.checker.get_user_role_codes` 查 DB，不从 JWT payload 读 | payload 不含 roles（已核实）；core/rbac 是核心基础设施（非业务模块 Repository），与既有装饰器同源，无跨模块 Repository 越界 |
| D2 | 新增 `get_user_role_codes` 而非 3 次 `check_role` | 单次查询；复用 `check_roles` 既有 SQL 模式；非授权决策（仍返回集合给 Service 分流），授权边界不动 |
| D3 | 角色优先级 admin > student > teacher | admin 全量；非 admin 时 student 强制 own（最严格，防学员伪装教师窥探）；非 admin 非 student 时 teacher 按其排期；无任何三者 → 默认按 own（最小权限默认） |
| D4 | `get_booking_by_id` 用 owner OR teacher-of-schedule OR admin 三选一放行 | owner 始终能查自己（即使有 teacher 角色也能查自己作为学员的预约）；teacher 查其排期下任意学员预约；admin 全量。语义清晰、最小惊讶 |
| D5 | teacher 分支用 `BookingRepository.search(teacher_id=...)` JOIN 实现 | 单查询、避免"先查 schedule_ids 再 IN"两段式；JOIN 路径与既有 `upcoming` 一致；`idx_schedules_teacher_start` 索引可命中 |
| D6 | `_get_schedule_info_map` 补 `teacher_id` 字段做归属校验 | 该函数已 SELECT `CourseSchedule.teacher_id`，仅返回值未含；补字段零额外查询、零响应泄露（`_to_response` 不消费） |
| D7 | Router 删除 `student_id` 推导，仅透传 `current_user` | 遵守"Router 不写业务判断"；身份透传与既有 `cancel_booking` 一致 |
| D8 | MCP `get_my_bookings` 改透传 `current_user`、删除 `student_id=user_id` | student 用户行为不变（Service 强制 student_id=user_id）；teacher 用户改为见自己排期预约（符合 T2.2.3）；统一归属逻辑，MCP 不另搞一套 |
| D9 | 不在 JWT payload 塞 roles | 那会扩大到 auth 模块 + 刷新/吊销策略，应单独立项；本 Feature 用 DB 查询，单次查询走既有 RBAC + 权限缓存基础设施 |
| D10 | 非授权角色的未知用户默认按 own 过滤 | 最小权限默认；避免"无角色 → 全量"的越权回归 |

## Dependency Analysis

- 复用：`app.core.rbac.checker`（新增 1 个查询函数）；`BookingRepository`/`ScheduleRepository`（既有）；`_get_schedule_info_map`（既有，补字段）。
- 角色查询带租户上下文：`get_user_role_codes` 用 `or_(Role.tenant_id == tid, Role.tenant_id.is_(None))`，与 `check_roles` 一致，兼容全局角色（如 super_admin）。
- 无新外部依赖；无 DB 结构变更；无 Redis key 结构变更。
- 契约：OpenAPI 路径/方法/查询参数/请求体/响应模型全部不变；`current_user` 是 `Depends(get_current_user)` 注入，不出现在 OpenAPI → 无需 `pnpm gen:types`，前端 4 端无影响。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| `list_bookings` 签名变更影响 MCP `get_my_bookings` | 中 | 同步更新 mcp_server.py 调用；student 行为不变（测试 AC-8 验证） |
| admin 端管理页若依赖"学员传 schedule_id 看全部"的旧行为 | 低 | admin 角色不受 student 分支影响（admin 全量）；学员端本就不应看他人预约 |
| 教师调用 `get_my_bookings` 行为由"空"改为"其排期预约" | 低 | 符合 T2.2.3 预期；release-note 说明 |
| `get_user_role_codes` 单次查询性能 | 低 | 单条 JOIN 查询；权限缓存不影响角色查询（角色集合较小）；list 接口本身已有 student_map/schedule_map 批量查询，归属查询占比低 |
| 无角色用户被默认按 own 过滤导致看不到数据 | 低 | 这正是最小权限默认；实际生产中学员/教师/管理员必居其一 |
| 测试依赖种子数据中的 student/teacher/admin 用户 | 中 | 复用 conftest 种子（13800000001 super_admin / 13800138001 teacher / 13900139001 student）；测试内创建额外学员 + 排期 + 预约 |

## Implementation Steps

1. `core/rbac/checker.py` 加 `get_user_role_codes` → py_compile。
2. `booking/repository.py` `search` 加 `teacher_id` → py_compile。
3. `booking/service.py` 三处改动 → py_compile。
4. `booking/router.py` 两处透传 → py_compile。
5. `ai/mcp_server.py` 同步调用 → py_compile。
6. 静态审查 diff（仅允许上表 6 个文件）。
7. 编写 `test_booking_ownership.py`，迭代至全绿。
8. 回归：`test_auth_api.py`、`test_rbac_enforcement.py`、`test_admin_user_real.py`。

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1~6, 10, 11 | `pytest tests/integration/test_booking_ownership.py -v` |
| AC-7 | 回归 `test_auth_api.py` + `test_rbac_enforcement.py` + `test_admin_user_real.py` |
| AC-8 | `test_booking_ownership.py` 中 student 用例 + service 直调断言 |
| AC-9 | 静态 grep：router 无 `role`/`student` 判断分支 |
| AC-12 | 既有 `TenantAwareRepository` 行为（不新增测试） |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他仓库内脚本/工具直接调 `BookingService.list_bookings`/`get_booking_by_id`（不经 router/mcp） | grep 已确认仅 router + mcp 两处调用 + 示例文档；如有遗漏，新 `current_user` 为 keyword-only 必选参数会在调用处报 TypeError，静态可发现 |
| U2 | 教师既被分配 student 角色又会触发哪个分支 | D3 优先级：student 赢 → 教师看不到自己排期下的他人预约（只能看自己作为学员的预约）。生产中教师不应同时持有 student 角色；如确有此场景，后续可加显式"切换视角"参数（不在本 Feature 范围） |
| U3 | 测试环境是否已有可用排期/预约种子 | conftest 仅种子用户/角色/权限，无排期/预约种子 → 测试内自建课程+教室+排期+预约，断言以本测试创建的数据为准 |
