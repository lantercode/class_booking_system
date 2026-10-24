# F2.5 — delete_schedule 下沉到 Service · 需求文档

> Feature ID：F2.5
> 作者：backend-engineer
> 日期：2026-09-28
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（纯后端分层重构，范围极小，走 v2 轨道，不召前端；不触 DB 结构 → 不召 database-engineer）
> 依赖：无（`BookingRepository.delete_by_schedule_id` 既有；`TenantAwareRepository.delete(hard_delete=True)` 既有）
> 前置 Feature：F2.4（cancel_schedule 事务回滚，已完成；本 Feature 参照同文件 `batch_delete_schedules` 的既有下沉模式）

---

## Goal

`DELETE /api/v1/schedules/{schedule_id}` 端点当前在 Router 层直接承载业务逻辑与数据访问，违反 `.trae/rules/architecture/layering.md` 的标准调用链（Router → Service → Repository）：

- Router 直调 `schedule_service.repo.get_by_id(...)`（绕过 Service）；
- Router 内联存在性判断与"NORMAL 且 booked_count>0 拒绝删除"业务规则；
- Router 直调**其他模块**的 `BookingRepository().delete_by_schedule_id(...)`（跨模块直连 Repository，双重违规）；
- Router 直调 `schedule_service.repo.delete(..., hard_delete=True)`。

修复目标：将删除逻辑原样下沉到 `ScheduleService.delete_schedule(db, schedule_id)`，Router 瘦身为"参数提取 + 调 Service + 返回信封"的薄层。**行为零变化、OpenAPI 契约零变化、前端 4 端零改动。**

## User Story

作为维护该代码库的后端工程师，
我希望删除排期的业务规则与数据访问只存在于 Service 层，以便：

- Router 层不持有业务判断（存在性、状态 + booked_count 规则），符合分层强制规则，代码审查有统一标准。
- 其他调用方（未来的 MCP Tool / 定时任务 / 批量任务）可以复用同一个 `delete_schedule` Service 方法，获得同样的规则校验与事务边界，而不必复制 Router 内联逻辑。
- 跨模块访问 booking 表的代码集中在 schedule Service（与同文件 `batch_delete_schedules` 同构），消除"Router 直调他模块 Repository"的边界破例。

作为系统，
我希望 `delete_schedule` 单删路径与既有 `batch_delete_schedules` Service 路径使用同一套校验与删除顺序（booking 先删、schedule 硬删、同事务 commit），以便单删与批删行为一致、可审计。

## Background / 现状（已核查的代码事实）

| 事实 | 证据 |
|------|------|
| Router 直调本模块 Repository | [router.py:211](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/router.py#L211)（重构前）：`schedule = await schedule_service.repo.get_by_id(db, schedule_id)` |
| 业务规则在 Router | [router.py:212-221](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/router.py#L212-221)（重构前）：不存在 → `NotFoundException`；`status == NORMAL and booked_count > 0` → `BusinessException(code=400)` |
| Router 直调他模块 Repository | [router.py:224-227](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/router.py#L224-227)（重构前）：函数内 `from app.modules.booking.repository import BookingRepository` + `await booking_repo.delete_by_schedule_id(db, schedule_id)` |
| Router 直调 repo.delete 硬删 | [router.py:229](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/router.py#L229)（重构前）：`await schedule_service.repo.delete(db, schedule_id, hard_delete=True)` |
| 同文件已有下沉参照 | router L240 `batch_delete_schedules` → service `ScheduleService.batch_delete_schedules(db, schedule_ids, tenant_id)`：Service 内做存在性 / 状态 / booked_count 校验 + `BookingRepository().delete_by_schedule_id` + `self.repo.delete(hard_delete=True)` |
| `BookingRepository.delete_by_schedule_id` 行为 | [booking/repository.py:185-200](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L185-200)：执行 `Booking.__table__.delete()`（硬删，无状态过滤，同排期任意状态 booking 均删），**不 commit**；ContextVar 有租户时追加 `tenant_id` 过滤 |
| `TenantAwareRepository.delete` 事务语义 | [core/base_repository.py:316-353](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/base_repository.py#L316-353)：`hard_delete=True` 走主键硬删；`auto_commit=True`（默认）删除后 `await db.commit()`；异常时 `await db.rollback()` 并 raise |
| 外键约束 | [booking/models.py:36-40](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L36-40)：`bookings.schedule_id → course_schedules.id ON DELETE RESTRICT` → 必须先删 booking 再删 schedule，这是删除顺序存在的原因 |
| Service 顶部已 import 异常类 | [service.py:14](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L14)：`from app.core.exceptions import BusinessException, NotFoundException, ValidationException` → 无需新增 import |
| Router 顶部 `ScheduleStatus` 仅删除端点使用 | grep 确认：重构前 router.py 中 `ScheduleStatus` 仅 L12 import + L218 使用；`NotFoundException` / `BusinessException` / `BookingRepository` 均为端点内局部 import |

## Scope（In Scope）

1. `schedule/service.py`：新增 `delete_schedule(self, db, schedule_id) -> dict[str, Any]`，逻辑从 router L211-229 **原样迁移**：
   - `self.repo.get_by_id` → 不存在 raise `NotFoundException("排期不存在")`；
   - `status == ScheduleStatus.NORMAL.value and booked_count > 0` → raise `BusinessException("该排期仍有学员预约，请先取消排期后再删除", code=400)`；
   - 函数内 import `BookingRepository`（与 `batch_delete_schedules` / `cancel_schedule` 现有风格一致）→ `delete_by_schedule_id(db, schedule_id)`；
   - `await self.repo.delete(db, schedule_id, hard_delete=True)`（沿用 `auto_commit=True`，与 batch 路径一致；两步删除由该 commit 统一提交）；
   - `logger.info` 记录删除成功；返回 `{"schedule_id": schedule_id}`。
2. `schedule/router.py`：`delete_schedule` 端点瘦身为薄层（仅调 `schedule_service.delete_schedule(db, schedule_id)` + `return success(msg="排期删除成功")`）；删除仅此处使用的顶部 import `ScheduleStatus`（端点内局部 import 随方法体一并消失）。
3. 新增集成测试 `apps/api/tests/integration/test_delete_schedule_service.py`：9 用例，覆盖 Service 直调 3 条 AC + HTTP 3 条 AC + 3 个补充场景。

## Out of Scope

- 不修改 `booking` 模块（`BookingRepository.delete_by_schedule_id` 既有，直接复用）。
- 不修改 `schedule/repository.py` / `models.py` / `schemas.py`。
- 不重构 `batch_delete_schedules`（其 Service 内仍直调 `BookingRepository`，严格按 layering 规则也属于"跨模块应走对方 Service"的历史模式，但与单删路径现状同构；统一改造属另一个技术债 Feature，本 Feature 不扩大范围）。
- 不改变任何业务规则（错误码、错误文案、删除顺序、硬删语义、commit 时机全部保持）。
- 不修改 OpenAPI 契约（`DELETE /schedules/{schedule_id}` 路径 / 方法 / 权限 `schedule:delete` / 响应模型 `dict` / 响应 msg 不变）。
- 不修改前端 4 端（admin-web / student-web / teacher-web / miniapp）。
- 不修改 MCP（无 `delete_schedule` Tool）。
- 不修改 DB 结构、不写 migration、不引入新依赖。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1：Service 直调删除已取消排期成功，返回 `{"schedule_id": id}`，关联 booking 被级联硬删（DB 断言 schedule / booking 均不存在）。
- AC-2：Service 直调删除不存在排期 → `NotFoundException`（404 "排期不存在"）。
- AC-3：Service 直调删除 NORMAL 且 booked_count>0 排期 → `BusinessException(code=400)`，msg 含"仍有学员预约"；DB 中 schedule 与 booking 均无变更。
- AC-4：HTTP admin `DELETE /schedules/{id}` → 200，`code=0`，`msg="排期删除成功"`；DB 中 schedule / booking 被硬删。
- AC-5：HTTP student（无 `schedule:delete` 权限）→ 403；schedule 不被删除。
- AC-6：HTTP 删除不存在排期 → 404 业务错误信封（`code=404`，msg 含"不存在"，无 Traceback）。
- AC-7：回归 `test_cancel_schedule_rollback.py` + `test_checkin_complete_lock.py` + `test_booking_ownership.py` + `test_auth_api.py` 全量通过。
- AC-8：分层合规——router.py 不再出现 `BookingRepository` / `repo.get_by_id` / `repo.delete` / 业务异常判断；端点仅参数提取 + 调 Service。

## Dependencies

- 复用：`BookingRepository.delete_by_schedule_id`（既有，硬删 + 不 commit + 租户过滤）。
- 复用：`ScheduleRepository.get_by_id` / `TenantAwareRepository.delete(hard_delete=True, auto_commit=True)`（既有）。
- 参照：同文件 `ScheduleService.batch_delete_schedules` 的下沉模式。
- 无新外部依赖；无 DB 结构变更；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响。

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他调用方依赖 router 内联删除逻辑（不经端点） | 内联逻辑位于端点函数体内，Python 层面不可能被外部复用；下沉后仅 `ScheduleService.delete_schedule` 一个权威实现。grep 确认仓库内无其他 `delete(hard_delete=True)` 单删排期调用方 |
| U2 | 两步删除（booking DELETE 未 commit → schedule DELETE → commit）的原子性 | 两步共享请求级同一 `AsyncSession`，位于同一事务；`repo.delete(auto_commit=True)` 统一 commit；若 schedule 删除抛错（如残留 RESTRICT 外键），base_repository 的 except 执行 `db.rollback()`，booking 的 DELETE 一并回滚 |
| U3 | Service 内函数级 `from ...BookingRepository import` 是否应改为顶部 import | 与同文件 `cancel_schedule` / `batch_delete_schedules` 现有风格保持一致（函数内 import 用于规避模块循环加载的历史约定）；本 Feature 不引入新风格，待后续统一整理 |
