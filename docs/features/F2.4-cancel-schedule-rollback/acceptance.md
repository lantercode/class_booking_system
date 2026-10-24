# F2.4 — cancel_schedule 回补失败回滚 · 验收标准

> 每条 AC 均可通过集成测试（`tests/integration/test_cancel_schedule_rollback.py`）或回归测试验证。
> 测试入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_cancel_schedule_rollback.py -v`

| # | AC | 验证方式 | 预期 |
|---|----|---------|------|
| AC-1 | 正常取消（含 booking+card）→ 全部 CANCELLED + credit 恢复 | IT：构造 1 schedule(booked_count=1) + 1 BOOKED booking + 1 ACTIVE card(used_credits=1)；Service 直调 `cancel_schedule` | raise 无；返回 `{total_bookings:1, success_count:1, failed_count:0, failed_bookings:[]}`；DB 终态 schedule=CANCELLED、booked_count=0、booking=CANCELLED、`cancelled_at` 非空、card.used_credits=0（恢复 1→0） |
| AC-2 | restore_credit 失败 → 整体回滚 | IT：同 AC-1 数据；`monkeypatch.setattr(MembershipCardService, "restore_credit", _fail_restore)` 抛 RuntimeError | `cancel_schedule` raise `BusinessException(code=500)`，msg 含"会员卡恢复次数失败"与"取消排期操作已撤销"；mock 调用计数==1；DB 终态 schedule=NORMAL、booked_count=1、booking=BOOKED、`cancelled_at`=None、card.used_credits=1（未恢复） |
| AC-3 | 多 booking 中途失败 → 已成功变更也回滚 | IT：1 schedule(booked_count=2) + 2 不同 student 的 BOOKED booking + 2 card(各 used_credits=1)；mock 第 2 次调用 restore_credit 抛异常 | `cancel_schedule` raise `BusinessException(500)`；mock 调用计数==2；DB 终态 schedule=NORMAL、booked_count=2、两 booking 都仍 BOOKED、两 `cancelled_at` 都仍 None、两 card.used_credits 都仍 1 |
| AC-4 | 无 BOOKED 预约 → 直接成功 | IT：1 schedule(booked_count=0, 无 booking)；Service 直调 | 返回 `{total_bookings:0, success_count:0, ...}`；DB 终态 schedule=CANCELLED |
| AC-5 | 已 CANCELLED 排期再取消 → 400 | IT：1 schedule(status=CANCELLED)；Service 直调 | raise `BusinessException(code=400)`，msg 含"已取消" |
| AC-6 | HTTP 正常取消 → 200 + 信封正确 | IT：同 AC-1 数据；HTTP `POST /schedules/{id}/cancel`（super_admin token） | 200；body.code=0；data 字段 {schedule_id, total_bookings:1, success_count:1, failed_count:0}；msg 非空且不含 Traceback；DB 终态正确 |
| AC-7 | HTTP 失败路径 → 500 + 信封 + DB 回滚 | IT：构造 used_credits=0 的卡触发 `restore_credit` 真实抛 HTTPException(400) → 内层 except 包装为 BusinessException(500) | 500；body.code=500；msg 含"会员卡恢复次数失败"与"取消排期操作已撤销"；msg 不含 Traceback / RuntimeError / HTTPException；DB 终态 schedule=NORMAL、booked_count=1、booking=BOOKED、`cancelled_at`=None、card.used_credits=0（原本就是 0，未变） |
| AC-8 | 回归不破现有行为 | 回归：`test_checkin_complete_lock.py` + `test_booking_ownership.py` + `test_auth_api.py` | 全部通过 |
| AC-9 | 分层合规 | 静态：Service 调 `repo.decrement_booked_count` 与 `booking_repo.search`（不裸 SQL）；`db.commit()` 在 Service；跨模块仅调 `MembershipCardService.restore_credit`；router 无业务判断 | 无违规 |

## 辅助断言（用于加强 AC-2/AC-3 的可信度）

- AC-2a：mock 调用计数==1（异常抛出后循环立即终止，不继续处理后续 booking）。
- AC-3a：mock 调用计数==2（第一个成功，第二个失败）。
- AC-3b：第一个 booking 的 `cancelled_at` 在事务回滚后为 None（已设置的值被回滚）。
- AC-7a：响应 body 不含内部异常类型字符串（`RuntimeError` / `HTTPException` / `asyncpg` / `sqlalchemy`）。
- AC-7b：响应 body 不含 Traceback（即 `"Traceback" not in body["msg"]` 且 `"Traceback" not in str(body)`）。

## HTTP 状态码与信封约定（对照 contracts.md）

- 业务错误同时体现在 HTTP 状态码与响应体 `code` 字段（`{code:500, msg, data:null}`）。
- 后端不向前端回传 traceback / 内部堆栈 / SQL / 异常类型字符串。
- 401 处理由前端 API 层统一处理；本 Feature 不引入新的 401 行为。
