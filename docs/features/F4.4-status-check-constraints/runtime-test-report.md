# F4.4 — 运行时测试报告

> 日期：2026-10-02
> 环境：本地开发机，PostgreSQL（Docker 共享开发库，预置种子租户 dance-school），Redis 可用。migration `f44ab1c2d3e4` 已 apply（alembic_version=f44ab1c2d3e4）。

## 1. 测试入口

```bash
# 主测试（F4.4）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_status_check_constraints.py -v

# 回归（AC-11，F4.1 + F4.2 不被破坏）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_fk_membership_card.py tests/integration/test_order_fk_membership_card.py -v
```

## 2. 结果摘要

| 套件 | 结果 |
|------|------|
| `test_status_check_constraints.py` | **18 passed**（0.66s） |
| `test_booking_fk_membership_card.py`（F4.1 回归） | **6 passed**（0.32s） |
| `test_order_fk_membership_card.py`（F4.2 回归） | **7 passed**（0.28s） |
| **合计** | **31 passed, 2 warnings** |

warnings 均为既有第三方库 deprecation（passlib `crypt`、FastAPI `example`），与本 Feature 无关。

## 3. 用例明细（test_status_check_constraints.py，18/18 通过）

### 3.1 TestStatusCheckConstraintsExist（约束存在性，3/3）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_check_constraint_exists[ck_bookings_status]` | AC-1 | 查询 `pg_constraint` 取 `pg_get_constraintdef`；定义含 `CHECK` 与全部合法值 `1,2,3,4,5` |
| `test_check_constraint_exists[ck_course_schedules_status]` | AC-2 | 同上；合法值 `1,2,3` |
| `test_check_constraint_exists[ck_membership_cards_status]` | AC-3 | 同上；合法值 `0,1,2,3,6` |

### 3.2 TestStatusCheckConstraintsEnforced（非法值拒绝 + 合法值放行，12/12）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_booking_invalid_status_rejected[0]` | AC-4 | `Booking(status=0)` → `pytest.raises(IntegrityError)`；非法 booking 未落库 |
| `test_booking_invalid_status_rejected[6]` | AC-4 | `Booking(status=6)` → `pytest.raises(IntegrityError)` |
| `test_booking_invalid_status_rejected[99]` | AC-4 | `Booking(status=99)` → `pytest.raises(IntegrityError)` |
| `test_schedule_invalid_status_rejected[0]` | AC-5 | `CourseSchedule(status=0)` → `pytest.raises(IntegrityError)` |
| `test_schedule_invalid_status_rejected[4]` | AC-5 | `CourseSchedule(status=4)` → `pytest.raises(IntegrityError)` |
| `test_schedule_invalid_status_rejected[99]` | AC-5 | `CourseSchedule(status=99)` → `pytest.raises(IntegrityError)` |
| `test_card_invalid_status_rejected[4]` | AC-6 | `MembershipCard(status=4)` → `pytest.raises(IntegrityError)` |
| `test_card_invalid_status_rejected[5]` | AC-6 | `MembershipCard(status=5)` → `pytest.raises(IntegrityError)` |
| `test_card_invalid_status_rejected[99]` | AC-6 | `MembershipCard(status=99)` → `pytest.raises(IntegrityError)` |
| `test_booking_valid_statuses_succeed` | AC-7 | 落库 `status=1,3,5`（BOOKED/CHECKED_IN/NO_SHOW）；重读等于预期 |
| `test_schedule_valid_statuses_succeed` | AC-8 | 落库 `status=1,2,3`（NORMAL/CANCELLED/FINISHED）；重读等于预期 |
| `test_card_valid_statuses_succeed` | AC-9 | 落库 `status=0,1,2,3,6`（PENDING/ACTIVE/EXPIRED/FROZEN/CANCELLED）；重读等于预期 |

### 3.3 TestExistingDataIntact（存量数据未破坏，3/3）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_no_out_of_range_status_and_data_present[bookings]` | AC-10 | `WHERE status NOT IN (1,2,3,4,5)` 行数 == 0；总数 > 0（实测 11） |
| `test_no_out_of_range_status_and_data_present[course_schedules]` | AC-10 | `WHERE status NOT IN (1,2,3)` 行数 == 0；总数 > 0（实测 33） |
| `test_no_out_of_range_status_and_data_present[membership_cards]` | AC-10 | `WHERE status NOT IN (0,1,2,3,6)` 行数 == 0；总数 > 0（实测 17） |

## 4. 测试可信度分析

### 4.1 测试逻辑的区分力

- **migration 未应用前**：`test_check_constraint_exists` 查不到约束 → 3 个失败；`test_booking_invalid_status_rejected[99]` 等插入不抛 IntegrityError（无 Check） → 9 个失败。
- **migration 应用后**：上述用例全部通过 → 证明 Check 约束已建。
- 若回退本 Feature（drop 三约束），`test_check_constraint_exists` + `test_*_invalid_status_rejected` 必失败。

### 4.2 真实 DB 事务性保障

- 非法值用例：独立 session `session.add` + `session.commit` → PostgreSQL check_violation → SQLAlchemy `IntegrityError` → `session.rollback()`；再独立 session 重查确认非法行未落库。
- 合法值用例：独立 session `add/flush/commit` → 再独立 session `SELECT` 验证终态（避免 dirty read）。
- AC-7 booking 合法值用独立 schedule（`capacity=77` 测试标记值）避免 `uq_bookings_schedule_student_active` 部分唯一索引冲突。

### 4.3 事件循环隔离（借鉴 F4.1 / F4.2）

- `shared_data`（session-scoped）在 session loop 内创建并 dispose engine，只返回纯数据 dict。
- `local_db`（function-scoped）为每用例独立 engine + session_factory。
- AC-7/8/9 合法值测试在独立 fixture 引擎内完成，finally cleanup 清理测试行。

18/18 全绿，无跨 loop 错误。

## 5. 回归结论

- `test_booking_fk_membership_card.py`（F4.1，6/6）：全部通过 → AC-11 满足。
- `test_order_fk_membership_card.py`（F4.2，7/7）：全部通过 → AC-11 满足。
- 本 Feature 不动 bookings/orders 的 FK / 索引，仅新增三张表的 status Check → F4.1/F4.2 行为不受影响。
- Service/Repository 零改动 → 业务逻辑零回归风险。

## 6. 性能与资源

- 18 个主测试用例约 0.66s（含 fixture 一次性解析种子 IDs + 每用例独立数据创建/清理）。
- 全部 31 用例（含回归）约 1.26s，无慢查询告警。
- Check 约束对正常写入的开销极低（PG 对 `CHECK (status IN (...))` 为小常数整数比较，无索引查找）。

## 7. 迭代记录

| 轮次 | 问题 | 修复 |
|------|------|------|
| 第 1 轮 | — | **18/18 通过**（首版即全绿，无迭代） |
