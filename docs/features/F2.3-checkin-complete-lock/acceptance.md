# F2.3 — 签到/完成加行锁 · 验收标准

> 每条 AC 均可通过集成测试（`tests/integration/test_checkin_complete_lock.py`）或回归测试验证。
> 测试入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_checkin_complete_lock.py -v`

| # | AC | 验证方式 | 预期 |
|---|----|---------|------|
| AC-1 | 并发签到只成一个 | IT：booking 处于 `BOOKED`；`asyncio.gather` 同时发起 2 个 `POST /bookings/{id}/check-in` | 恰好一个 200，另一个 400 且 `msg` 含"无法签到"；DB 终态 `CHECKED_IN`（不重复） |
| AC-2 | 并发完成只成一个 | IT：booking 处于 `BOOKED`；`asyncio.gather` 同时发起 2 个 `POST /bookings/{id}/complete` | 恰好一个 200，另一个 400 且 `msg` 含"无法完成"；DB 终态 `COMPLETED` |
| AC-3 | 正常单签到成功 | IT：booking 处于 `BOOKED`；单请求 `POST /bookings/{id}/check-in` | 200；返回 data.status=`CHECKED_IN`；`checked_in_at` 非空 |
| AC-4 | 正常单完成成功 | IT：booking 处于 `BOOKED`；单请求 `POST /bookings/{id}/complete` | 200；返回 data.status=`COMPLETED` |
| AC-5 | 已签到再签到失败 | IT：booking 已 `CHECKED_IN`；再调 `POST /bookings/{id}/check-in` | 400；`msg` 含"无法签到" |
| AC-6 | 已完成再完成失败 | IT：booking 已 `COMPLETED`；再调 `POST /bookings/{id}/complete` | 400；`msg` 含"无法完成" |
| AC-7 | 回归不破现有行为 | 回归：`test_booking_ownership.py` + `test_auth_api.py` | 全部通过 |
| AC-8 | 分层合规 | 静态：service 调 `repo.get_by_id_for_update`（不裸 SQL）；`db.commit()` 在 Service；router 无业务判断 | 无违规 |

## 辅助断言（用于加强 AC-1/AC-2 的可信度）

- AC-1a：并发签到后，DB 中该 booking 的 `checked_in_at` 仅被设置一次（非空且单调）。
- AC-2a：并发完成后，DB 中该 booking 的 `status == COMPLETED`（不会因并发回退到 BOOKED）。
- AC-1b/AC-2b：失败的那个请求响应体符合统一信封 `{code:400, msg:"...", data:null}`，不回显 traceback。
