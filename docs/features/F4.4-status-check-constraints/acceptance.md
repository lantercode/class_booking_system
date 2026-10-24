# F4.4 — 核心表 status 字段 Check 约束 · 验收标准

> 每条 AC 均可通过集成测试（`tests/integration/test_status_check_constraints.py`）验证。
> 测试入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_status_check_constraints.py -v`

| # | AC | 验证方式 | 预期 |
|---|----|---------|------|
| AC-1 | `ck_bookings_status` 存在且定义正确 | IT：查询 `pg_constraint` 取 `pg_get_constraintdef(oid)`，且 `contype='c'` | 定义含 `CHECK` 与全部合法值 `1,2,3,4,5` |
| AC-2 | `ck_course_schedules_status` 存在且定义正确 | IT：同上 | 定义含 `CHECK` 与全部合法值 `1,2,3` |
| AC-3 | `ck_membership_cards_status` 存在且定义正确 | IT：同上 | 定义含 `CHECK` 与全部合法值 `0,1,2,3,6` |
| AC-4 | bookings 插入非法 status → IntegrityError | IT：`Booking(status=0/6/99)` 分别 `session.add` + `commit` | `pytest.raises(IntegrityError)`；非法行未落库 |
| AC-5 | course_schedules 插入非法 status → IntegrityError | IT：`CourseSchedule(status=0/4/99)` 同上 | 同上 |
| AC-6 | membership_cards 插入非法 status → IntegrityError | IT：`MembershipCard(status=4/5/99)` 同上 | 同上 |
| AC-7 | bookings 合法边界 + 中间值 → 成功 | IT：落库 `status=1,3,5`（BOOKED/CHECKED_IN/NO_SHOW） | 均成功；重读 `status` 等于预期 |
| AC-8 | course_schedules 合法值 → 成功 | IT：落库 `status=1,2,3`（NORMAL/CANCELLED/FINISHED） | 同上 |
| AC-9 | membership_cards 合法边界 + 中间值 → 成功 | IT：落库 `status=0,1,2,3,6`（PENDING/ACTIVE/EXPIRED/FROZEN/CANCELLED） | 同上 |
| AC-10 | 存量数据未被破坏 | IT：`WHERE status NOT IN (...)` 行数 == 0；且存量 `COUNT(*)` > 0 | 三表越界均为 0；数据行数不变 |
| AC-11 | 回归不破现有行为 | 回归：`test_booking_fk_membership_card.py`（F4.1）+ `test_order_fk_membership_card.py`（F4.2） | 全部通过（6+7 = 13/13） |
| AC-12 | 分层合规 | 静态：Service/Repository/Router/schemas 零改动；模型与 migration 一致 | 无违规 |
| AC-13 | migration 可逆 | `alembic downgrade -1` → 三约束消失、alembic_version=f42cd3e4f5a6；`alembic upgrade head` → 三约束恢复、alembic_version=f44ab1c2d3e4 | 往返成功 |

## 辅助断言

- AC-1a：三个约束名在 `pg_constraint` 的 `conname` 中精确匹配。
- AC-4a/5a/6a：`IntegrityError` 由 PostgreSQL check_violation 在 commit 时抛出（asyncpg → SQLAlchemy），非业务层手写校验。
- AC-7a/8a/9a：合法值落库后通过独立 `AsyncSession` 重读（避免读到 dirty session）。
- AC-10a：三表总 `COUNT(*)` 在 migration 前后一致（实测 bookings=11 / course_schedules=33 / membership_cards=17）。

## HTTP 状态码与信封约定（对照 contracts.md）

- 本 Feature 无 HTTP 端点变更，无新增信封/状态码。
- `IntegrityError` 不会直接透传给前端：经全局异常处理器返回统一信封 `{code:500, msg, data:null}`，不回显 SQL/traceback。
