# F2.4 — Review

> 日期：2026-09-28 ｜ 审查人：backend-engineer（自审 + 规则清单）

## Scope

- 变更严格限于 Feature 定义：`schedule/service.py` 的 `cancel_schedule` 一处方法体重构（移除外层 try/except；内层 except 改 raise `BusinessException(500)`；移除 `success_count` / `failed_bookings` 累加；`bookings[0]` → `bookings, _` 解构；补 docstring + 注释；返回 dict 字段集合兼容）+ 新增测试 `test_cancel_schedule_rollback.py`。
- `create_schedule` / `update_schedule` / `batch_delete_schedules` / `get_schedule_by_id` / `list_schedules` 等其他方法**未动**。
- Router / Repository / models / schemas / OpenAPI / 前端 / MCP **均未改动**。
- 未引入新依赖、未改 DB 结构、未改 OpenAPI 路径/方法/请求体/响应模型。

## Architecture

- Router → Service → Repository 分层合规：Service 调 `booking_repo.search`（取 BOOKED 预约，含租户过滤）、`self.repo.decrement_booked_count`（行锁封装在 Repository）、`self.repo.update`（更新 schedule 状态）；不裸用 `with_for_update`、不裸 SQL。
- 跨模块复用走 Service：`cancel_schedule` 调 `MembershipCardService.restore_credit`，不直接操作 membership Repository / 表；`restore_credit` 内部 `get_card_with_lock` 行锁封装在 MembershipCardService 内。
- 事务边界在 Service：`db.commit()` 在 L314（正常路径执行）；异常路径不到达 commit → AsyncSession 被 `with` 退出 / FastAPI 依赖清理时被动 rollback → 全部变更不落地。
- 与既有 `BookingService._do_cancel_booking` 事务模型同构（[booking/service.py:198-272](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L198-272)），事务边界统一、可审计。

## Code

- `cancel_schedule`：移除外层 try/except → for 循环内异常直接传播；内层 try/except 仅捕获 `restore_credit` 失败 → `raise BusinessException(f"会员卡恢复次数失败，取消排期操作已撤销: {e}", code=500)`，与 `_do_cancel_booking` L262-266 完全同构。
- `bookings = await ...; booking_list = bookings[0]` → `bookings, _ = await ...` 解构（`BookingRepository.search` 返回 `(list, total)` tuple；解构比 `[0]` 语义清晰，零行为变更）。
- 移除 `success_count` / `failed_bookings` 累加（事务回滚后无意义）；返回 dict 字段集合保留兼容（正常路径下 `success_count == total_bookings`，`failed_count == 0`，`failed_bookings == []`）。
- 补 docstring 明确事务边界模型；for 循环前补注释说明回滚语义。
- 未改 status 分支条件（CANCELLED → 400 / FINISHED → 400 / 不存在 → 404），未改 Service 签名 → 对调用方透明。

## Security

- 端点 `@require_permissions("schedule:cancel")` 原样保留（Router 未动）；身份 `current_user = Depends(get_current_user)` 不变；学员无此权限 → 403（测试 `test_http_cancel_schedule_unauthorized_fails` 验证）。
- 租户隔离：`ScheduleRepository` / `BookingRepository` 均继承 `TenantAwareRepository`，查询自动注入 `tenant_id`；`MembershipCardService.restore_credit` 内部 `get_card_with_lock` 含 `tenant_id` 过滤 → 跨租户 card_id 返回 404。
- 不存在 schedule_id → 404"排期不存在"（测试 `test_cancel_schedule_nonexistent_returns_404` / `test_http_cancel_schedule_nonexistent_returns_404` 验证，不泄露存在性）。
- 失败响应符合统一信封 `{code:500, msg:"...", data:null}`，不回显 traceback / SQL / 异常类型字符串（HTTP 测试 `test_http_cancel_schedule_restore_failure_rolls_back` 断言 `"Traceback" not in body["msg"]` / `"RuntimeError" not in body["msg"]` / `"HTTPException" not in body["msg"]`）。

## Transaction / Concurrency

- **核心修复**：消除 `cancel_schedule` 的"外层吞异常导致脏提交"数据不一致。
  - 修复前：restore_credit 失败 → 外层 except 接住 → `failed_bookings.append(...)` → 循环继续 → `db.commit()` 提交已变更的 booking.status / booked_count 但 credit 未恢复 → 脏数据。
  - 修复后：restore_credit 失败 → 内层 except 包装为 `BusinessException(500)` → raise 传播出方法 → `db.commit()` 永不执行 → AsyncSession ROLLBACK → 全部变更回滚。
- 多 booking 场景：第一个 restore 成功（事务内 INSERT txn，card.used_credits 减 1）+ 第二个失败 → 整体回滚 → 第一个的 INSERT txn 也回滚 → 幂等键查询回到初始状态（测试 `test_cancel_schedule_partial_failure_rolls_back_prior_success` 验证 mock 调用计数==2 + 两 booking 都仍 BOOKED + 两 card.used_credits 都仍 1）。
- 行锁：`decrement_booked_count` 内 `with_for_update` 按主键 `course_schedules.id` 命中；`restore_credit` 内 `get_card_with_lock` 按主键 `membership_cards.id` 命中。锁生命周期由 AsyncSession 管理，commit（正常路径）或 rollback（异常路径）后释放，无锁泄漏。
- 幂等键：`idempotency_key = f"schedule_cancel_{booking.id}_{schedule_id}"`，由 `restore_credit` 内部 `txn_repo.get_by_idempotency_key` 查 DB txn。事务回滚后 INSERT 的 txn 也回滚 → 幂等键回到初始状态 → 下次重试不会因幂等短路而漏回补。

## Regression

- `test_checkin_complete_lock.py`（9/9）+ `test_booking_ownership.py`（10/10）+ `test_auth_api.py`（25/25）：**44/44 通过** → AC-8 满足。
- 签到/完成行锁、预约归属、JWT 双 token / 黑名单 / refresh、RBAC 行为未受影响。
- 本 Feature 仅重构 `cancel_schedule` 事务模型（异常传播触发回滚），未改 Service 签名 / 端点契约 / 状态机分支 → 回归零风险。

## Acceptance

- AC-1（正常取消）：`test_cancel_schedule_normal_ok`（Service 直调）+ `test_http_cancel_schedule_normal_ok`（HTTP）通过。
- AC-2（restore 失败 → 整体回滚）：`test_cancel_schedule_restore_credit_failure_rolls_back_all`（monkeypatch）+ `test_http_cancel_schedule_restore_failure_rolls_back`（真实失败）通过。
- AC-3（多 booking 中途失败 → 已成功变更也回滚）：`test_cancel_schedule_partial_failure_rolls_back_prior_success` 通过。
- AC-4（无 BOOKED 预约 → 直接成功）：`test_cancel_schedule_no_bookings_ok` 通过。
- AC-5（已 CANCELLED → 400）：`test_cancel_schedule_already_cancelled_fails` + `test_http_cancel_schedule_already_cancelled_fails` 通过。
- AC-6（HTTP 正常 → 200 + 信封）：`test_http_cancel_schedule_normal_ok` 通过。
- AC-7（HTTP 失败 → 500 + 信封 + 无 Traceback + DB 回滚）：`test_http_cancel_schedule_restore_failure_rolls_back` 通过。
- AC-8（回归）：44/44 通过。
- AC-9（分层合规）：静态 grep 验证 Service 调 `repo.decrement_booked_count` 与 `booking_repo.search`、跨模块仅调 `MembershipCardService.restore_credit`、无裸 `with_for_update` / `db.execute` 直写、`db.commit()` 在 Service（详见 [static-verification.md](./static-verification.md)）。

## 遗留事项（不阻塞）

1. `cancel_schedule` 当前 `page_size=1000` 上限：单排期 BOOKED 预约数超过 1000 时会漏处理。实际排期容量通常远小于 1000，属另一优化 Feature 范围（按 capacity 分页或分批处理），本 Feature 不扩大范围。
2. `cancel_schedule` 当前未对"已 CHECKED_IN / COMPLETED 的预约"特殊处理：仅查 `status=BOOKED` 的预约取消并回补。若排期下有 CHECKED_IN 预约，`cancel_schedule` 不会取消它们（仍保持 CHECKED_IN 状态），但 schedule.status 会变 CANCELLED。这是既有行为，本 Feature 未改。建议后续 Feature 复核"取消排期对 CHECKED_IN 预约的处置策略"。
3. `cancel_schedule` 与 `BookingService._do_cancel_booking` 都未对"取消排期后通知学员"做处理（无通知系统），属 F6.2 通知系统范围。

## 结论

**READY_FOR_ACCEPTANCE**
