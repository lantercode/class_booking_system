# F2.5 — delete_schedule 下沉到 Service · 验收标准

> 每条 AC 均可通过集成测试（`tests/integration/test_delete_schedule_service.py`）或回归测试 / 静态 grep 验证。
> 测试入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_delete_schedule_service.py -v`

| # | AC | 验证方式 | 预期 |
|---|----|---------|------|
| AC-1 | Service 直调删除已取消排期成功，关联 booking 级联硬删 | IT：直接落库 1 schedule(status=CANCELLED, booked_count=0) + 1 booking(status=CANCELLED)；Service 直调 `delete_schedule` | 无 raise；返回值 == `{"schedule_id": schedule_id}`；新 session 查 DB：schedule 不存在、booking 不存在（硬删） |
| AC-2 | 删除不存在排期 → 404 | IT：schedule_id=999999999；Service 直调 | raise `NotFoundException`，str 含"不存在"（全局处理器映射 HTTP 404） |
| AC-3 | NORMAL 且 booked_count>0 → 400，DB 无变更 | IT：1 schedule(status=NORMAL, booked_count=1) + 1 booking(BOOKED)；Service 直调 | raise `BusinessException`，`code == 400`，msg 含"仍有学员预约"与"先取消排期后再删除"；DB：schedule 仍存在、booking 仍存在（规则判断先于任何 DELETE） |
| AC-4 | HTTP admin 删除成功 → 200 + 信封 | IT：同 AC-1 数据；`DELETE /api/v1/schedules/{id}`（super_admin token + x-tenant-slug） | HTTP 200；`body.code == 0`；`body.msg == "排期删除成功"`；响应无 Traceback；DB：schedule / booking 均不存在 |
| AC-5 | HTTP 无权限角色 → 403 | IT：seed student（仅 `booking:view`）token 删除 CANCELLED 排期 | HTTP 403；DB：schedule 仍存在（装饰器在业务逻辑前拦截，Service 未被调用） |
| AC-6 | HTTP 删除不存在 → 业务错误信封 | IT：`DELETE /api/v1/schedules/999999999`（super_admin） | HTTP 404；`body.code == 404`；msg 含"不存在"；整个 body 不含"Traceback" |
| AC-7 | 回归不破现有行为 | 回归：`test_cancel_schedule_rollback.py` + `test_checkin_complete_lock.py` + `test_booking_ownership.py` + `test_auth_api.py` | 全部通过（56/56） |
| AC-8 | 分层合规（本 Feature 的核心交付） | 静态：grep `apps/api/src/app/modules/schedule/router.py` 中 `BookingRepository` / `\.repo\.` / `get_by_id` / `hard_delete` / `delete_by_schedule_id` | 0 匹配；端点函数体仅 `await schedule_service.delete_schedule(db, schedule_id)` + `return success(...)`；装饰器 / 路径 / Docstring 保留 |

## 补充覆盖用例（加强行为零变化的可信度）

| 用例 | 验证点 |
|------|--------|
| `test_delete_normal_schedule_without_bookings_ok` | NORMAL 但 booked_count=0 且无 booking 行 → 放行硬删（规则只拦截"NORMAL 且 >0"），DB 中 schedule 不存在 |
| `test_delete_finished_schedule_ok_cascades_bookings` | FINISHED 排期 + COMPLETED booking → 放行；`delete_by_schedule_id` 无状态过滤，历史 booking 一并硬删 |
| `test_http_delete_normal_with_bookings_returns_400` | HTTP 路径的业务规则分支：400 信封 + msg 双片段断言 + 无 Traceback + schedule/booking DB 无变更 |

## 行为等价性说明（重构前后逐条对照）

| 行为点 | 重构前（router 内联） | 重构后（service） | 等价 |
|--------|----------------------|-------------------|------|
| 不存在 / 跨租户 | `NotFoundException("排期不存在")` | 同文案、同异常类型（默认 404） | ✅ |
| 拦截规则 | `status == NORMAL.value and booked_count > 0` | 条件表达式逐字一致 | ✅ |
| 拦截文案 / 码 | `"该排期仍有学员预约，请先取消排期后再删除", code=400` | 逐字一致 | ✅ |
| booking 删除 | `BookingRepository().delete_by_schedule_id(db, schedule_id)` | 同一方法、同一参数 | ✅ |
| schedule 删除 | `schedule_service.repo.delete(db, schedule_id, hard_delete=True)` | `self.repo.delete(db, schedule_id, hard_delete=True)`（同一实例方法，auto_commit 默认值不变） | ✅ |
| 事务 | delete_by_schedule_id 不 commit，repo.delete 统一 commit | 完全相同的 session 与提交时机 | ✅ |
| 成功响应 | `success(msg="排期删除成功")` | router 保留该行，未动 | ✅ |
| 路径 / 方法 / 权限 | `DELETE /schedules/{id}` + `@require_permissions("schedule:delete")` | 装饰器与路由声明零改动 | ✅ |

## HTTP 状态码与信封约定（对照 contracts.md）

- 业务错误同时体现在 HTTP 状态码与响应体 `code`：404 → `{code:404,...}`；400 → `{code:400,...}`。
- 后端不向前端回传 traceback / 内部堆栈 / SQL（AC-4 / AC-6 / 补充 HTTP 400 用例均断言 `"Traceback" not in str(body)`）。
- 401 / 403 行为由认证与 RBAC 既有链路统一处理，本 Feature 不新增分支。
