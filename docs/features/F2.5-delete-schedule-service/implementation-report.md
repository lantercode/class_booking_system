# F2.5 — delete_schedule 下沉到 Service · 实施报告

> 日期：2026-09-28 ｜ 执行：backend-engineer
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

按 [implementation-plan.md](./implementation-plan.md) 完成 `delete_schedule` 由 Router 到 Service 的原样下沉：`schedule/service.py` 新增 `delete_schedule(db, schedule_id) -> dict[str, Any]`（存在性校验 → NORMAL+booked_count 业务规则 → 先删关联 booking → 硬删 schedule → 同事务统一 commit）；`schedule/router.py` 端点瘦身为单行 Service 调用并移除唯一使用点的 `ScheduleStatus` 顶部 import。两个子任务 T2.5.1 / T2.5.2 全部交付。OpenAPI 契约、权限、响应 msg、错误码与文案零变化；booking 模块、repository、前端、MCP、DB 结构均未改动。首轮测试 9/9 即全绿，无迭代返工。

## 2. 变更明细

### 2.1 `apps/api/src/app/modules/schedule/service.py`（新增方法，L332-364）

- 位置：`cancel_schedule` 之后、`batch_delete_schedules` 之前（删除类操作聚拢）。
- 逻辑与重构前 router L211-229 逐行对应：

| 步骤 | 实现 | 对应重构前 |
|------|------|-----------|
| 存在性 | `schedule = await self.repo.get_by_id(...)`；None → `raise NotFoundException("排期不存在")` | router L211-215 |
| 业务规则 | `if schedule.status == ScheduleStatus.NORMAL.value and schedule.booked_count > 0:` → `raise BusinessException("该排期仍有学员预约，请先取消排期后再删除", code=400)` | router L217-221（条件 / 文案 / code 逐字一致） |
| 级联删 booking | 函数内 `from app.modules.booking.repository import BookingRepository`；`await BookingRepository().delete_by_schedule_id(db, schedule_id)` | router L223-227（import 风格与同文件 `batch_delete_schedules` 一致） |
| 硬删 schedule | `await self.repo.delete(db, schedule_id, hard_delete=True)`（auto_commit 默认 True，统一提交两步删除） | router L229 |
| 日志 / 返回 | `logger.info("[ScheduleService] ✅ 排期删除成功: id=...")`；`return {"schedule_id": schedule_id}` | 新增（不改变端点响应；router 仍返回 `success(msg="排期删除成功")`） |

- 未新增顶部 import：`BusinessException` / `NotFoundException`（service L14）与 `ScheduleStatus`（service L18）均已存在。
- 未修改任何既有方法（diff 中 service.py 的其余变化属于工作区前序 F2.4 未提交改动，非本 Feature）。

### 2.2 `apps/api/src/app/modules/schedule/router.py`（端点瘦身 + import 清理）

```diff
- from app.modules.schedule.models import ScheduleStatus
...
 async def delete_schedule(...):
     """删除排期"""
-    schedule = await schedule_service.repo.get_by_id(db, schedule_id)
-    if not schedule:
-        from app.core.exceptions import NotFoundException
-        raise NotFoundException("排期不存在")
-    if schedule.status == ScheduleStatus.NORMAL.value and schedule.booked_count > 0:
-        from app.core.exceptions import BusinessException
-        raise BusinessException("该排期仍有学员预约，请先取消排期后再删除", code=400)
-    from app.modules.booking.repository import BookingRepository
-    booking_repo = BookingRepository()
-    await booking_repo.delete_by_schedule_id(db, schedule_id)
-    await schedule_service.repo.delete(db, schedule_id, hard_delete=True)
+    await schedule_service.delete_schedule(db, schedule_id)
     return success(msg="排期删除成功")
```

- 路由声明（`@router.delete("/{schedule_id}", response_model=dict, ...)`）、`@require_permissions("schedule:delete")`、函数签名、Docstring 全部保留。
- `ScheduleStatus` 经 grep 确认为删除端点唯一使用点，移除顶部 import；`NotFoundException` / `BusinessException` / `BookingRepository` 原本是端点内局部 import，随函数体一并消失，router 其余端点不受影响。

### 2.3 `apps/api/tests/integration/test_delete_schedule_service.py`（新建，9 用例）

- **fixture（复用 F2.4 模式）**：session 级 `delete_data`（1 共享 course + 解析 tenant / seed student / admin ID；engine 在 fixture 内 dispose，仅回传纯数据 dict；无需临时 student——每用例独立 schedule，不触唯一约束）；function 级 `local_db`（每用例独立 engine + session_factory，绑定用例事件循环）。
- **helper**：`_create_schedule` / `_create_booking`（直接落库，显式 `set_tenant_id`）、`_exists`（新 session 读已提交数据判定硬删）、`_cleanup`（先 booking 后 schedule，每步独立 session + commit）。
- **Service 直调 5 用例**：CANCELLED+booking 级联硬删 / 不存在 → NotFound / NORMAL+booked_count=1 → 400 且双表无变化 / NORMAL+0 预约放行 / FINISHED+COMPLETED booking 放行并级联。
- **HTTP 4 用例**：admin 200（msg 严格等于"排期删除成功"+ 双表 DB 断言）/ student 403（schedule 仍存在）/ 不存在 404 信封 / NORMAL+预约 400 信封（无 Traceback + 双表无变化）。

## 3. 实施中发现的问题

| # | 问题 | 处置 |
|---|------|------|
| 1 | 工作区中 service.py / repository.py / scheduler.py 含前序 Feature 未提交改动 | 实施前先 `git diff` 识别边界；只做定点编辑（service 追加方法、router 两处）；未 commit、未 stash、未覆盖任何他人改动；在本报告与 plan 中显式记录 |
| 2 | FINISHED 排期下的 COMPLETED booking 是否会被级联删除需锁定（`delete_by_schedule_id` 无状态过滤） | 补补充用例 `test_delete_finished_schedule_ok_cascades_bookings`，固化"非 NORMAL 放行 + 全状态 booking 硬删"的既有行为 |

无测试驱动返工：首轮执行 9/9 通过。

## 4. 与计划的偏差

- 无。计划列出的 3 个文件（service 追加 / router 瘦身 / 新测试）全部按 Exact Fix 交付；未新增计划外源文件改动。

## 5. 数据兼容与迁移

- 无 DB 结构变更，无 migration。
- 无配置 / 环境变量 / Redis key 变更。
- OpenAPI 零变化：`DELETE /api/v1/schedules/{schedule_id}` 的路径、方法、权限 `schedule:delete`、`response_model=dict`、成功信封 `{code:0,msg:"排期删除成功",data:null}` 与 400/404 错误信封全部不变 → 无需 `pnpm gen:types`，前端 4 端零改动。

## 6. 测试结果

- `test_delete_schedule_service.py`：**9 passed**（1.66s，首轮即全绿）
- 回归 `test_cancel_schedule_rollback.py`（12）+ `test_checkin_complete_lock.py`（9）+ `test_booking_ownership.py`（10）+ `test_auth_api.py`（25）：**56 passed**（13.05s）
- 合计 **65 passed**，无 failure / error；warnings 均为既有第三方 deprecation（passlib crypt / websockets legacy / FastAPI example）。

详见 [runtime-test-report.md](./runtime-test-report.md)。
