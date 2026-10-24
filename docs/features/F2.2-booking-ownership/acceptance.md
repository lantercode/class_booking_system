# F2.2 — 预约数据归属与泄露修复 · 验收标准

> 每条 AC 均可通过集成测试（`tests/integration/test_booking_ownership.py`）或回归测试验证。
> 测试入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_ownership.py -v`

| # | AC | 验证方式 | 预期 |
|---|----|---------|------|
| AC-1 | 学员按 schedule_id 查仍只看自己 | IT：学员 A 创建预约后，学员 B 调 `GET /bookings?schedule_id=<该排期>` | B 的 items 不含 A 的预约；A 自己调则命中 |
| AC-2 | 学员查他人预约详情被拒 | IT：学员 A 调 `GET /bookings/{B 的预约 id}` | 403，msg 含"无权查看" |
| AC-3 | 学员列表只返回自己 | IT：A、B 各有预约；A 调 `GET /bookings` | items 的 `student_id` 全部 == A 的 user_id |
| AC-4 | 教师列表只返回其排期下的预约 | IT：教师 T 名下排期有学员预约；非 T 排期也有预约；T 调 `GET /bookings` | items 的 `schedule_id` 全部 ∈ T 名下 schedule_ids；不含他人排期 |
| AC-5 | 教师查/拒他人排期预约详情 | IT：T 调 `GET /bookings/{其排期下 id}` → 200；调 `GET /bookings/{他人排期 id}` → 403 | 200 / 403 |
| AC-6 | 管理员全量可查 | IT：super_admin 调 `GET /bookings` 与 `GET /bookings/{任意 id}` | 200；items 含跨学员数据 |
| AC-7 | 认证/RBAC/admin 真实化回归 | 回归：`test_auth_api.py` + `test_rbac_enforcement.py` + `test_admin_user_real.py` | 全部通过 |
| AC-8 | MCP 行为（student 不变） | 单元/集成：student 用户经 `BookingService.list_bookings(current_user=...)` | 仍只返回该 student 自己的预约 |
| AC-9 | 分层合规 | 静态：grep router 无角色判断分支；service 调 `get_user_role_codes`；不直写跨模块 Repository | 无违规 |
| AC-10 | 学员 owner 始终能查自己 | IT：A 调 `GET /bookings/{A 自己的预约 id}` | 200 |
| AC-11 | 不存在预约 404 | IT：A 调 `GET /bookings/999999999` | 404，msg 含"不存在" |
| AC-12 | 跨租户不可见 | 静态/既有：`BookingRepository.get_by_id` 继承 `TenantAwareRepository`，ORM 事件自动注入 `tenant_id` | 跨租户 booking_id → 404（非 403，不泄露存在性） |
