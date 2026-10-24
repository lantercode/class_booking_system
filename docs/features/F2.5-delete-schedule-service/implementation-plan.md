# F2.5 — delete_schedule 下沉到 Service · 实施方案

> Feature ID：F2.5
> 作者：backend-engineer
> 日期：2026-09-28
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

`DELETE /schedules/{schedule_id}` 端点在 Router 层同时承担了参数注入、业务规则判断与数据访问，违反 `.trae/rules/architecture/layering.md`「Router 只允许做参数提取与 Pydantic 校验、依赖注入、调用 Service、返回响应」与系统边界第 4 条「跨模块复用业务能力时调用对方模块的 Service，禁止直接写其他模块的 Repository」：

1. **Router 直调本模块 Repository**：重构前 router L211 `schedule = await schedule_service.repo.get_by_id(db, schedule_id)`、L229 `await schedule_service.repo.delete(db, schedule_id, hard_delete=True)`。
2. **业务规则位于 Router**：重构前 L212-215 存在性 → `NotFoundException`；L218-221 `NORMAL + booked_count>0` → `BusinessException(400)`。
3. **Router 直调他模块 Repository（双重违规）**：重构前 L224-227 函数内 `from app.modules.booking.repository import BookingRepository` 并执行 `delete_by_schedule_id`。

**对照**：同文件 `batch_delete_schedules` 端点已是正确形态——router 仅取参 + 调 `schedule_service.batch_delete_schedules(db, schedule_ids, tenant_id)`；校验与删除顺序全在 Service。本 Feature 让单删路径与之同构。

## 已核查的代码事实（Evidence）

| 事实 | 证据 |
|------|------|
| 单删端点内联全部逻辑 | [router.py:198-230](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/router.py#L198-230)（重构前） |
| 批删端点已下沉（参照模式） | router `batch_delete_schedules` → [service.py `batch_delete_schedules`](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py)：存在性 / 租户 / `NORMAL+booked_count` 校验 + `BookingRepository().delete_by_schedule_id` + `self.repo.delete(hard_delete=True)` |
| booking 级联删除语义 | [booking/repository.py:185-200](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L185-200)：`Booking.__table__.delete().where(schedule_id==...)`，无状态过滤；ContextVar 有租户时加 tenant 条件；只 execute 不 commit |
| 硬删 + 提交 / 回滚语义 | [core/base_repository.py:316-353](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/base_repository.py#L316-353)：hard_delete 主键 DELETE；`auto_commit=True` → `db.commit()`；except → `db.rollback(); raise` |
| 外键决定删除顺序 | [booking/models.py:36-40](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L36-40)：`schedule_id FK ON DELETE RESTRICT` → 必须先删 booking |
| Service 已含所需 import | [service.py:14](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L14) 已 import `BusinessException` / `NotFoundException`；L18 已 import `ScheduleStatus` |
| Router 顶部 ScheduleStatus 唯一使用点 | grep 确认重构前仅 L12 import + 删除端点 L218 使用；其余端点不引用 → 可安全移除顶部 import |
| 状态枚举 | [schedule/models.py:12-15](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/models.py#L12-15)：`NORMAL=1 / CANCELLED=2 / FINISHED=3` |
| 种子 RBAC | conftest：super_admin 持全部权限（含 `schedule:delete`）；student 仅持 `booking:view` → 可直接验证 403 |

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/modules/schedule/service.py` | 新增 `delete_schedule` 方法（插入于 `cancel_schedule` 与 `batch_delete_schedules` 之间，L332-364）；无既有代码修改 |
| 2 | `apps/api/src/app/modules/schedule/router.py` | `delete_schedule` 端点体由 20 行业务 / 数据访问缩为 1 行 Service 调用；移除顶部不再使用的 `from ...models import ScheduleStatus` |
| 3 | `apps/api/tests/integration/test_delete_schedule_service.py` | 新建，9 用例（Service 直调 5 + HTTP 4） |

**不在改动范围**：booking 模块 / schedule repository / models / schemas / OpenAPI / 前端 / MCP / DB 结构 / migration / Redis / `batch_delete_schedules`。

> 工作区说明：`schedule/service.py`、`schedule/repository.py`、`schedule/scheduler.py` 中存在**前序 Feature（F2.4 等）尚未 commit 的改动**，本 Feature 仅在 service.py 追加方法，未触碰那些既有改动，未执行任何 git commit / 破坏性操作。

## Exact Fix

### 1. `ScheduleService.delete_schedule`（service.py，新增）

```python
async def delete_schedule(
    self,
    db: AsyncSession,
    schedule_id: int,
) -> dict[str, Any]:
    """硬删除排期

    业务规则（原 router 逻辑原样下沉，行为零变化）：
    - 排期不存在 / 跨租户 → NotFoundException（404 "排期不存在"）。
    - 仅 NORMAL（待上课）状态且 booked_count > 0 时拒绝删除
      → BusinessException（400），需先取消排期。
    - 先删除该排期关联的 booking（避免外键约束冲突），再硬删 schedule；
      两步共享同一 AsyncSession，由 ``self.repo.delete(auto_commit=True)``
      统一 commit，异常时 Repository 内 rollback 并 raise。
    """
    schedule = await self.repo.get_by_id(db, schedule_id)
    if not schedule:
        raise NotFoundException("排期不存在")

    # 仅对待上课状态的排期检查学员预约
    if schedule.status == ScheduleStatus.NORMAL.value and schedule.booked_count > 0:
        raise BusinessException("该排期仍有学员预约，请先取消排期后再删除", code=400)

    # 删除关联的预约记录（避免外键约束冲突）
    from app.modules.booking.repository import BookingRepository

    booking_repo = BookingRepository()
    await booking_repo.delete_by_schedule_id(db, schedule_id)

    await self.repo.delete(db, schedule_id, hard_delete=True)

    logger.info(f"[ScheduleService] ✅ 排期删除成功: id={schedule_id}")
    return {"schedule_id": schedule_id}
```

### 2. router 端点（重构后完整）

```python
@router.delete(
    "/{schedule_id}",
    response_model=dict,
    summary="删除排期",
    description="硬删除排期（需 schedule:delete 权限）",
)
@require_permissions("schedule:delete")
async def delete_schedule(
    schedule_id: int = Path(..., description="排期ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """删除排期"""
    await schedule_service.delete_schedule(db, schedule_id)
    return success(msg="排期删除成功")
```

路由装饰器（路径 / 方法 / response_model / summary / description）、`@require_permissions("schedule:delete")`、签名、Docstring、成功响应全部保留；仅函数体变化 + 删除顶部 `ScheduleStatus` import。

## 关键决策记录（Decision）

| # | 决策 | 理由 |
|---|------|------|
| D1 | 逻辑原样迁移，不"顺手修正" | 本 Feature 是分层重构而非行为变更：错误文案、code、条件表达式、删除顺序、硬删 / commit 语义逐字保留，保证零行为风险；测试锁定等价性 |
| D2 | 返回 `dict[str, Any]`（`{"schedule_id": id}`）而非 None | 与任务契约一致，且与 Service 其他写方法（`cancel_schedule` / `batch_delete_schedules` 均返回 dict）风格统一；为未来调用方（MCP Tool 需要结构化回执）预留 |
| D3 | `BookingRepository` 保持函数内 import | 与同文件 `cancel_schedule` / `batch_delete_schedules` 的历史风格一致（规避循环加载）；新增顶部 import 反而是风格破例。跨模块"应走 booking Service"的更严格收口登记为技术债，不在本 Feature |
| D4 | 不向方法传 `tenant_id` / `current_user` | 租户来自 ContextVar（Middleware → ORM 事件 / `delete_by_schedule_id` 内 `get_tenant_id()`），不信任调用方入参，符合 tenant-isolation.md；原 router 也未传 tenant_id，行为等价 |
| D5 | 事务仍由 `repo.delete(auto_commit=True)` 统一提交 | booking DELETE 与 schedule DELETE 在同一 session 同一事务；与 `batch_delete_schedules` 完全一致；不额外加 `db.commit()`（否则变成两次提交，破坏原子性） |
| D6 | 移除 router 顶部 `ScheduleStatus` import | grep 确认删除端点是唯一使用点；`NotFoundException` / `BusinessException` / `BookingRepository` 本就是端点内局部 import，随函数体一并消失，无需改顶部 |
| D7 | 不改 OpenAPI / 前端 / MCP / DB | 纯内部代码位移；端点路径 / 方法 / 权限 / 响应模型 / msg 零变化 |

## Dependency Analysis

- 复用（零修改）：`BookingRepository.delete_by_schedule_id`、`ScheduleRepository.get_by_id`、`TenantAwareRepository.delete`。
- 无新外部依赖；无 DB 结构变更；无 Redis / 配置 / 环境变量变更；无 OpenAPI 变更 → 无需 `pnpm gen:types`。
- 前端 4 端影响评估：契约零变化（`DELETE /schedules/{id}` 200/400/404/403 的状态码与信封不变）→ admin-web / teacher-web / student-web / miniapp 均**不涉及**。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 迁移过程中改错业务条件 / 文案 / code | 低 | 条件与文案逐字复制；AC-3 / HTTP 400 用例对 code=400 与文案双片段做断言 |
| 提交时机变化导致 booking 与 schedule 非原子 | 低 | 沿用同一 session 且不新增 commit；AC-1 用新 session 双表断言硬删；base_repository 异常 rollback 语义已存在 |
| 租户上下文在 Service 直调路径缺失 | 低 | HTTP 路径由 Middleware 注入 ContextVar；Service 直调测试在 session 内 `set_tenant_id`；与 F2.4 测试同模式 |
| 顶部 `ScheduleStatus` import 误删导致其他端点 NameError | 低 | grep 确认唯一使用点；py_compile + 全量 router 导入（live_server 启动即覆盖）+ 9 用例运行验证 |
| 工作区前序未提交改动被污染 | 低 | 仅 2 处定点编辑（service 追加分方法 / router 2 处）；diff 已逐段复核，未触碰 repository.py / scheduler.py |
| FINISHED 排期带历史 booking 的删除行为 | 低 | 既有逻辑即"非 NORMAL 一律放行 + 全状态 booking 硬删"；补充用例 `test_delete_finished_schedule_ok_cascades_bookings` 锁定，防止下沉时被误改 |

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1 | `test_delete_cancelled_schedule_ok_cascades_bookings`（Service 直调 + 双表 DB 断言） |
| AC-2 | `test_delete_nonexistent_schedule_raises_not_found` |
| AC-3 | `test_delete_normal_schedule_with_bookings_raises_business_no_change`（code/文案 + 双表仍存在） |
| AC-4 | `test_http_delete_cancelled_schedule_ok`（200 + msg 严格相等 + DB 断言） |
| AC-5 | `test_http_delete_schedule_forbidden_for_student`（403 + schedule 仍存在） |
| AC-6 | `test_http_delete_nonexistent_returns_business_error`（404 信封 + 无 Traceback） |
| AC-7 | 回归四套件（56 用例） |
| AC-8 | py_compile + grep router.py 0 匹配（详见 static-verification.md） |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 仓库内是否存在绕过端点的单删调用方 | 端点函数体内联逻辑不可能被外部复用；下沉后 grep `delete_schedule(` 仅 router 与 service 定义/调用；MCP 无该 Tool |
| U2 | schedule DELETE 失败时 booking DELETE 是否确定回滚 | 两语句同 session 同事务；`TenantAwareRepository.delete` except 中 `await db.rollback()` 覆盖整个事务；AC-1 证明成功路径，RESTRICT 触发回滚为 base_repository 既有保证 |
| U3 | 是否要把 `BookingRepository` 访问收口为 booking Service 方法 | 严格按 layering「跨模块只调对方 Service」应收口；但 `cancel_schedule` / `batch_delete_schedules` 现状同构，单独立项改造更安全，本 Feature 保持同构并在 release-note 登记技术债 |
