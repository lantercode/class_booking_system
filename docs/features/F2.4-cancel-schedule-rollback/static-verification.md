# F2.4 — 静态验证报告

> 日期：2026-09-28

## 1. py_compile

```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
  src/app/modules/schedule/service.py \
  tests/integration/test_cancel_schedule_rollback.py
# → COMPILE_OK_ALL（全部通过，无输出错误）
```

实际执行：

```
$ cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile src/app/modules/schedule/service.py tests/integration/test_cancel_schedule_rollback.py && echo "COMPILE_OK_ALL"
COMPILE_OK_ALL
```

## 2. 改动落点核查（grep）

```bash
grep -n "try:\|except\|raise\|failed_bookings\|success_count\|db.commit\|decrement_booked_count\|restore_credit" \
  apps/api/src/app/modules/schedule/service.py
```

`cancel_schedule` 方法（L231-330）内的关键行：

| 行 | 调用 | 方法 | 结论 |
|----|------|------|------|
| L241-243 | docstring 注释 | "事务边界：本方法持有整个事务。任一 booking 处理失败（含 restore_credit 失败）都直接 raise，db.commit() 永不执行，AsyncSession 由 FastAPI 依赖清理时被动回滚..." | ✅ 事务模型说明 |
| L252 | `raise NotFoundException("排期不存在")` | schedule 不存在 / 跨租户 | ✅ 既有，保留 |
| L255 | `raise BusinessException("排期已取消", code=400)` | 状态校验 | ✅ 既有，保留 |
| L258 | `raise BusinessException("排期已完成，无法取消", code=400)` | 状态校验 | ✅ 既有，保留 |
| L267-273 | `bookings, _ = await booking_repo.search(...)` | 取 BOOKED 预约列表（含租户过滤） | ✅ 修复：`bookings[0]` → `bookings, _` 解构 |
| L277-278 | for 循环前注释 | "任一失败 → raise → db.commit() 永不执行 → AsyncSession 被动回滚 → 已变更的 booking 状态、decrement_booked_count、schedule 状态全部回滚" | ✅ 事务回滚语义说明 |
| L280-282 | `booking.status = CANCELLED; booking.cancelled_at = now; booking.cancelled_reason = ...` | booking 状态变更 | ✅ 直接赋值（无外层 try 包裹） |
| L284 | `await self.repo.decrement_booked_count(db, schedule_id)` | 排期人数 -1（含 FOR UPDATE） | ✅ 走 Repository |
| L289-296 | `try: await membership_card_service.restore_credit(...)` | 跨模块 Service 调用 | ✅ 走 MembershipCardService |
| L297-305 | `except Exception as e: logger.error(...); raise BusinessException(f"会员卡恢复次数失败，取消排期操作已撤销: {e}", code=500)` | 内层 except 包装 + raise | ✅ 与 `_do_cancel_booking` 同构 |
| L307-312 | `update_data = {...}; schedule = await self.repo.update(db, schedule_id, update_data)` | schedule 状态更新 | ✅ 走 Repository |
| L314 | `await db.commit()` | 事务提交（正常路径执行；异常路径不到达） | ✅ 事务边界在 Service |
| L324-329 | `return {schedule_id, total_bookings, success_count: total_bookings, failed_count: 0, failed_bookings: []}` | 返回字段集合兼容 | ✅ router 仍可消费 |

**结论**：本 Feature 改动精确落在 `cancel_schedule`（L231-330）一处方法体重构：
- 外层 try/except 已移除（grep 输出 L272-329 区域无外层 `try:` / `except` 包裹 for 循环）。
- 内层 try/except 仅用于捕获 `restore_credit` 失败 → `raise BusinessException(500)`。
- `db.commit()` 在 L314（正常路径），异常路径不到达。
- 返回 dict 字段集合不变（router 不动）。

## 3. 分层合规检查

```bash
# service 不裸用 with_for_update（行锁封装在 Repository）
grep -n "with_for_update\|db.execute\|session.execute" apps/api/src/app/modules/schedule/service.py
# 无匹配（行级锁封装在 ScheduleRepository.decrement_booked_count 与 MembershipCardService.get_card_with_lock）
```

| 规则 | 检查 | 结果 |
|------|------|------|
| Service 不裸用 `with_for_update` | 本 Feature 改动均调 `repo.decrement_booked_count`（行锁封装在 Repository）；restore_credit 内部 `get_card_with_lock` 也在 MembershipCardService 内 | ✅ |
| 无新增裸 SQL / `db.execute` | schedule service 内既有 `db.execute` 仅在 `_get_course_info_map` / `_get_teacher_info_map` / `_get_classroom_info_map`（只读批量查询，本 Feature 未新增） | ✅ |
| 事务边界在 Service | `await db.commit()` 在 L314（正常路径）；异常路径不到达 commit | ✅ |
| Repository 边界 | `decrement_booked_count` / `BookingRepository.search` / `ScheduleRepository.update` 均为 Repository 既有方法（含租户过滤）；Service 不绕过 Repository | ✅ |
| 跨模块复用只调 Service | 本 Feature 跨模块仅调 `MembershipCardService.restore_credit`，不直接操作 membership Repository / 表 | ✅ |
| 租户隔离 | `ScheduleRepository` / `BookingRepository` 均继承 `TenantAwareRepository`，查询自动注入 `tenant_id`；`MembershipCardService.restore_credit` 内部 `get_card_with_lock` 含 `tenant_id` 过滤 | ✅ |
| RBAC | 端点 `@require_permissions("schedule:cancel")` 原样保留（router 未动） | ✅ |
| 认证 | `current_user = Depends(get_current_user)` 原样保留 | ✅ |
| AI 边界 | 本 Feature 不涉及 MCP（`cancel_schedule` 不在 Tool 集合；AI 侧通过 `cancel_booking` Tool 取消单预约） | ✅ |

## 4. Diff 审查（改动面白名单）

```bash
git diff --stat -- apps/api/src/app/modules/schedule/service.py
# （本 Feature 改动 + 工作区其他未提交变更累计）
```

**本 Feature 实际触碰**：

| 文件 | 本 Feature 实际变化 | 审查结论 |
|------|------|---------|
| `apps/api/src/app/modules/schedule/service.py` | `cancel_schedule`（L231-330）：移除外层 try/except；内层 except 改 raise `BusinessException(500)`；移除 `success_count` / `failed_bookings` 累加；`bookings[0]` → `bookings, _` 解构；补 docstring + 注释；返回 dict 字段集合兼容 | 仅此一处方法体变更，行为：异常传播触发事务回滚 |
| `apps/api/tests/integration/test_cancel_schedule_rollback.py` | 新建 | 12 用例覆盖 AC-1~AC-7 + 补充场景 |

router.py / repository.py / models.py / schemas.py / OpenAPI / 前端 / MCP **均未改动**。

## 5. 契约一致性

- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变（`POST /schedules/{schedule_id}/cancel`，请求体 `ScheduleCancel{cancel_reason}`，响应 `dict`）。
- Service 签名 `cancel_schedule(db, schedule_id, cancel_reason, operator_id) -> dict[str, Any]` 不变 → Router 调用不变。
- 返回 dict 字段集合不变（`schedule_id` / `total_bookings` / `success_count` / `failed_count` / `failed_bookings`）→ router L192-193 仍可消费。
- 前端 4 端影响评估：`POST /schedules/{id}/cancel` 被 admin-web / teacher-web 消费，但**接口契约不变**（路径 / 方法 / 请求体 / 响应字段集合不变），仅事务语义更安全（失败回滚而非脏提交）→ 4 端均**无代码改动**。

## 6. 异常处理一致性

- 内层 `except Exception as e: raise BusinessException(f"会员卡恢复次数失败，取消排期操作已撤销: {e}", code=500)` 与 `_do_cancel_booking`（[booking/service.py:262-266](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L262-266)）完全同构。
- `BusinessException(code=500)` 经全局异常处理器返回 `{code:500, msg, data:null}` 信封，不回显 traceback / SQL / 内部异常类型字符串（见 HTTP 测试 `test_http_cancel_schedule_restore_failure_rolls_back` 断言 `"Traceback" not in body["msg"]` / `"RuntimeError" not in body["msg"]` / `"HTTPException" not in body["msg"]`）。
