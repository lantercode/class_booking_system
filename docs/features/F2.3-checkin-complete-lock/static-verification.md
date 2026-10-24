# F2.3 — 静态验证报告

> 日期：2026-09-28

## 1. py_compile

```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
  src/app/modules/booking/service.py \
  tests/integration/test_checkin_complete_lock.py
# → COMPILE_OK_ALL（全部通过，无输出错误）
```

## 2. 改动落点核查（grep）

```bash
grep -n "get_by_id_for_update\|get_by_id\b" apps/api/src/app/modules/booking/service.py
```

| 行 | 调用 | 方法 | 结论 |
|----|------|------|------|
| L63 | `self.schedule_repo.get_by_id(db, data.schedule_id)` | `create_booking` 取排期（只读，无锁） | ✅ 保留，不在本 Feature 范围 |
| L172 | `self.repo.get_by_id(db, booking_id)` | `cancel_booking` 取 stale 对象传入 `_do_cancel_booking`（锁在 `_do_cancel` 内重新取） | ✅ 保留，正确（cancel 既有锁模式） |
| L214 | `self.repo.get_by_id_for_update(db, booking.id)` | `_do_cancel_booking`（既有） | ✅ 既有，参照样板 |
| **L288** | `self.repo.get_by_id_for_update(db, booking_id)` | **`check_in_booking`（本 Feature）** | ✅ 已由 `get_by_id` 改为 `get_by_id_for_update` |
| L225 | `self.schedule_repo.get_by_id(db, locked_booking.schedule_id)` | `_do_cancel_booking` 取排期（只读） | ✅ 保留 |
| **L318** | `self.repo.get_by_id_for_update(db, booking_id)` | **`complete_booking`（本 Feature）** | ✅ 已由 `get_by_id` 改为 `get_by_id_for_update` |
| L352 | `self.repo.get_by_id(db, booking_id)` | `get_booking_by_id`（F2.2 只读，无锁） | ✅ 保留，正确（只读不需行锁） |

**结论**：本 Feature 改动精确落在 `check_in_booking`（L288）与 `complete_booking`（L318）两处，均为 `get_by_id` → `get_by_id_for_update`；其余 `get_by_id` 调用（只读路径 / cancel 取 stale 对象）正确保留。

## 3. 分层合规检查

```bash
# service 不裸用 with_for_update（行锁封装在 Repository）
grep -n "with_for_update\|db.execute\|session.execute" apps/api/src/app/modules/booking/service.py
# 472: result = await db.execute(query)        # _get_schedule_info_map（F2.2 既有批量查询，非行锁）
# 501: result = await db.execute(query)        # _get_schedule_info_map
# 508: teacher_result = await db.execute(teacher_query)  # _get_schedule_info_map
```

| 规则 | 检查 | 结果 |
|------|------|------|
| Service 不裸用 `with_for_update` | 本 Feature 改动均调 `repo.get_by_id_for_update`（行锁封装在 Repository） | ✅ |
| 无新增裸 SQL / `db.execute` | L472/501/508 均为 F2.2 既有 `_get_schedule_info_map` 批量查询，本 Feature 未新增 | ✅ |
| 事务边界在 Service | `await db.commit()` 在 L299（check_in）/ L328（complete） | ✅ |
| Repository 边界 | `get_by_id_for_update` 是 Repository 既有方法（含租户过滤）；Service 不绕过 Repository | ✅ |
| 跨模块复用只调 Service | 本 Feature 不涉及跨模块调用 | ✅ |
| 租户隔离 | `get_by_id_for_update` 已含 `tenant_id` 过滤（[repository.py:219-221](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L219-221)） | ✅ |
| RBAC | 端点 `@require_permissions("booking:manage")` 原样保留（router 未动） | ✅ |
| 认证 | `current_user = Depends(get_current_user)` 原样保留 | ✅ |
| AI 边界 | 本 Feature 不涉及 MCP（check_in/complete 不在 Tool 集合） | ✅ |

## 4. Diff 审查（改动面白名单）

```bash
git diff --stat -- apps/api/src/app/modules/booking/service.py
# apps/api/src/app/modules/booking/service.py | 203 ++++++++++++++++++++++------
# 1 file changed, 162 insertions(+), 41 deletions(-)
```

**注**：`git diff` 对比的是 HEAD，工作区存在其他 Feature 的未提交变更（F2.2 归属 + create_booking 容量校验重构等累计 162/41）。**本 Feature 实际触碰**：

| 文件 | 本 Feature 实际变化 | 审查结论 |
|------|------|---------|
| `apps/api/src/app/modules/booking/service.py` | `check_in_booking`（L275-303）：`get_by_id` → `get_by_id_for_update`；变量 `booking` → `locked_booking`；加并发安全注释与 docstring | 仅此一处方法体变更，行为：加行锁 + 重检 status（即拿到锁后读取） |
| 同上 | `complete_booking`（L305-332）：同上模式 | 仅此一处方法体变更 |
| `apps/api/tests/integration/test_checkin_complete_lock.py` | 新建 | 9 用例覆盖 AC-1~AC-6 + 补充场景 |

router.py / repository.py / models.py / schemas.py / OpenAPI / 前端 / MCP **均未改动**。

## 5. 契约一致性

- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变（`POST /bookings/{id}/check-in` / `POST /bookings/{id}/complete`）。
- Service 签名 `check_in_booking(db, booking_id)` / `complete_booking(db, booking_id)` 不变 → Router 调用不变。
- 响应字段集合不变（仍返回 `BookingResponse`）。
- 前端 4 端影响评估：`check-in` / `complete` 被 admin-web / teacher-web 消费（管理端签到/完成），但**接口契约不变**，仅并发行为更安全 → 4 端均**无代码改动**。

## 6. 变量名一致性

`check_in_booking` / `complete_booking` 内变量 `booking` → `locked_booking`，与 `_do_cancel_booking`（L214 `locked_booking`）命名同构，自文档化"后续操作均作用于 FOR UPDATE 锁定对象"。`_to_response(locked_booking)` 调用同步更新，行为不变。
