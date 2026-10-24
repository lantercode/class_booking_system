# F4.4 — 核心表 status 字段 Check 约束 · 实施报告

> 日期：2026-10-02 ｜ 执行：database-engineer
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

按 [implementation-plan.md](./implementation-plan.md) 完成 F4.4 四个子任务：
- **T4.4.1**：`bookings.status` Check 约束 `ck_bookings_status`（`IN (1,2,3,4,5)`）→ migration `create_check_constraint` + 模型补 `CheckConstraint`。
- **T4.4.2**：`course_schedules.status` Check 约束 `ck_course_schedules_status`（`IN (1,2,3)`）→ 同上。
- **T4.4.3**：`membership_cards.status` Check 约束 `ck_membership_cards_status`（`IN (0,1,2,3,6)`）→ 同上。
- **T4.4.4**：migration `f44ab1c2d3e4`（`down_revision=f42cd3e4f5a6`，F4.2 后唯一 head）→ upgrade 越界 fail-fast 校验 + 三约束；downgrade 反序 drop 三约束。

Service / Repository / Router / schemas / OpenAPI / 前端 / MCP 均未改动。

## 2. 变更明细

### 2.1 `apps/api/alembic/versions/f44ab1c2d3e4_add_status_check_constraints.py`（新建）

| 项 | 值 |
|----|-----|
| revision | `f44ab1c2d3e4` |
| down_revision | `f42cd3e4f5a6`（F4.2 后唯一 head） |
| upgrade | (1) `SELECT status, COUNT(*) ... WHERE status NOT IN (...)` 三表越界校验，fail-fast；(2) `op.create_check_constraint` x3 |
| downgrade | `op.drop_constraint(..., type_="check")` x3（反序） |

要点：
- 越界校验 + 建约束在同一事务（alembic `Will assume transactional DDL`），原子完成。
- 约束名显式 `ck_bookings_status` / `ck_course_schedules_status` / `ck_membership_cards_status`，便于 downgrade 精确 drop。
- `down_revision` 指向 `f42cd3e4f5a6`（F4.2），revision 链不断裂。
- 越界校验策略为 fail-fast（非 F4.1/F4.2 的防御性清理）：status 非法值无语义安全的自动修正目标，报错打印明细利于人工核查。

### 2.2 模型对齐（3 文件）

| 文件 | 改动点 | 修复后 |
|------|--------|--------|
| booking/models.py | `__table_args__` 新增 `CheckConstraint("status IN (1, 2, 3, 4, 5)", name="ck_bookings_status")`；import 补 `CheckConstraint` | 模型与 migration 一致 |
| schedule/models.py | `__table_args__` 首项新增 `CheckConstraint("status IN (1, 2, 3)", name="ck_course_schedules_status")` | 模型与 migration 一致 |
| membership/models.py | `__table_args__` 首项新增 `CheckConstraint("status IN (0, 1, 2, 3, 6)", name="ck_membership_cards_status")` | 模型与 migration 一致 |

### 2.3 `apps/api/tests/integration/test_status_check_constraints.py`（新建）

- session-scoped `shared_data` fixture：解析种子 IDs + 任一既有 course_id；engine 在 fixture 内 dispose。
- function-scoped `local_db` fixture：每用例独立 engine + session_factory。
- helper：`_gen_card_no` / `_create_schedule` / `_create_booking` / `_create_card` / `_cleanup`。
- 18 用例覆盖 AC-1~AC-10：
  - `TestStatusCheckConstraintsExist`：3 用例（parametrized，AC-1/2/3）
  - `TestStatusCheckConstraintsEnforced`：10 用例
    - `test_booking_invalid_status_rejected[0/6/99]`（AC-4，3 用例）
    - `test_schedule_invalid_status_rejected[0/4/99]`（AC-5，3 用例）
    - `test_card_invalid_status_rejected[4/5/99]`（AC-6，3 用例）
    - `test_booking_valid_statuses_succeed`（AC-7）
    - `test_schedule_valid_statuses_succeed`（AC-8）
    - `test_card_valid_statuses_succeed`（AC-9）
  - `TestExistingDataIntact`：3 用例（parametrized，AC-10）

## 3. 实施中发现的问题

| # | 问题 | 处置 |
|---|------|------|
| 1 | 三表 `status` 字段当前无 Check 约束，DB 无法拦截非法值 | 确认：本 Feature 即为修复；dev 库当前 0 越界但生产不可知 → migration 先做 fail-fast 校验再建约束 |
| 2 | `membership_cards` 既有 Check 命名漂移（模型 `chk_credits_range` vs DB `chk_used_credits_valid`/`chk_total_credits_positive`） | 确认：存量历史差异，不影响本 Feature；记入 UNKNOWN U3 |
| 3 | AC-7 排期合法值测试需真实 `course_id`（FK）与 `teacher_id`（FK） | `shared_data` 复用既有种子 course/teacher；不引入 mock FK |
| 4 | booking 合法值测试需独立排期（`uq_bookings_schedule_student_active` 部分唯一索引限定 `status IN (1,3,4)`） | 每个合法 booking 使用独立 schedule（`capacity=77` 测试标记值），避免 `student_id + schedule_id + status` 冲突 |

## 4. 与计划的偏差

- 计划列出的 4 个文件（migration + 3 模型 + 测试）全部按方案交付，无新增计划外源文件改动。
- 测试用例数 18（计划列 10 个 AC，parametrized 拆分为 18 个独立用例），与计划方向一致无冲突。
- 与 F4.1/F4.2 策略差异：本 Feature 越界校验采用 fail-fast（非防御性清理），在报告中作为 D2 关键决策透明记录。

## 5. 数据兼容与迁移

- **DB 结构变更**：新增 3 个 Check 约束（`ck_bookings_status` / `ck_course_schedules_status` / `ck_membership_cards_status`）。
- **数据变更**：无（Check 约束不修改存量数据）；dev 库 0 条越界通过校验；生产若有越界将 fail-fast 回滚。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。
- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变 → 无需 `pnpm gen:types`，前端 4 端无影响。
- migration 可逆（`downgrade` drop 三个 Check 约束；不恢复数据）。

## 6. 测试结果

- `test_status_check_constraints.py`：**18 passed**（0.66s）
- 回归 `test_booking_fk_membership_card.py`（F4.1）：**6 passed**（0.32s）
- 回归 `test_order_fk_membership_card.py`（F4.2）：**7 passed**（0.28s）
- migration 可逆性（`alembic downgrade -1` + `alembic upgrade head`）：往返成功，约束消失再恢复。
- py_compile（3 模型 + migration + 测试）：`COMPILE_OK_ALL`。
- `alembic heads`：单 head `f44ab1c2d3e4`（无分叉）。
- app import 冒烟：`from app.main import app` 成功；`Booking.__table__.constraints` 含 `ck_bookings_status`，其余两模型同。

详见 [runtime-test-report.md](./runtime-test-report.md) 与 [static-verification.md](./static-verification.md)。
