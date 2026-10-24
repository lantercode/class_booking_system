# F2.4 — cancel_schedule 回补失败回滚 · 实施报告

> 日期：2026-09-28 ｜ 执行：backend-engineer
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

按 [implementation-plan.md](./implementation-plan.md) 完成 `cancel_schedule` 回补失败回滚：移除 `cancel_schedule` 的外层 `try/except`（吞异常导致脏提交），内层 `except` 改为 `raise BusinessException(code=500, msg="会员卡恢复次数失败，取消排期操作已撤销: ...")`，与既有 `BookingService._do_cancel_booking` 同构。两个子任务 T2.4.1 / T2.4.2 全部交付。Service 签名不变，Router / Repository / OpenAPI / 前端 / MCP 均未改动。

## 2. 变更明细

### 2.1 `apps/api/src/app/modules/schedule/service.py`（`cancel_schedule` 方法体重构）

| 改动点 | 修复前（L231-322） | 修复后（L231-330） |
|--------|---------|---------|
| 外层 try/except | `for booking in booking_list: try: ... except Exception as e: failed_bookings.append(...)` —— 吞异常 | **移除** —— 异常直接传播出方法 |
| 内层 try/except | `try: await restore_credit(...) except Exception as e: logger.error(...); raise` —— raise 出去被外层接住 | `try: await restore_credit(...) except Exception as e: logger.error(...); raise BusinessException(f"会员卡恢复次数失败，取消排期操作已撤销: {e}", code=500)` —— 与 `_do_cancel_booking` 同构 |
| `success_count` / `failed_bookings` | 累加逻辑（事务回滚后无意义） | **移除累加**；返回 dict 字段集合保留兼容（正常路径下 `success_count == total_bookings`，`failed_count == 0`，`failed_bookings == []`） |
| `bookings` 取值 | `bookings = await ...; booking_list = bookings[0]` | `bookings, _ = await ...` 解构（语义清晰，零行为变更） |
| docstring | 简略"取消排期(含学员预约处理)" | 补充事务边界模型说明：异常传播 → `db.commit()` 永不执行 → AsyncSession 被动回滚 → 全部变更不落地 |
| 注释 | 无 | 在 for 循环前补注释明确"任一失败 → raise → db.commit() 永不执行 → AsyncSession 被动回滚" |

要点：
- 事务边界仍在 Service：`await db.commit()` 在 L314（正常路径执行；异常路径不到达）。
- 异常传播触发回滚是 SQLAlchemy 的标准事务模式；FastAPI 依赖清理（`get_session` 的 finally）会 rollback 未 commit 的 session。
- 返回 dict 字段集合不变 → router L192-193 仍可消费 `total_bookings` / `success_count` 构造 msg。
- `MembershipCardService.restore_credit` 自带幂等键（查 DB txn），事务回滚后 INSERT 的 txn 也回滚 → 幂等键回到初始状态 → 下次重试不会因幂等短路而漏回补。

### 2.2 `apps/api/tests/integration/test_cancel_schedule_rollback.py`（新建）

- session-scoped `rollback_data` fixture：搭建共享 course + 解析种子 IDs（super_admin / teacher / student / tenant）+ 通过 admin HTTP 创建 2 个临时 student（student_a / student_b）供多 booking 场景使用（规避 `uq_bookings_schedule_student_active` 唯一约束 `(schedule_id, student_id)`）。engine 在 fixture 内 dispose，只返回纯数据 dict。
- function-scoped `local_db` fixture：每用例独立 engine + session_factory，绑定当前用例事件循环。
- 12 用例覆盖 AC-1 ~ AC-7 + 补充场景：
  - **Service 直调路径**（7 用例）：`test_cancel_schedule_normal_ok` / `test_cancel_schedule_restore_credit_failure_rolls_back_all`（monkeypatch）/ `test_cancel_schedule_partial_failure_rolls_back_prior_success`（mock 第 2 次失败）/ `test_cancel_schedule_no_bookings_ok` / `test_cancel_schedule_already_cancelled_fails` / `test_cancel_schedule_finished_fails` / `test_cancel_schedule_nonexistent_returns_404`。
  - **HTTP 端点路径**（5 用例）：`test_http_cancel_schedule_normal_ok` / `test_http_cancel_schedule_restore_failure_rolls_back`（真实失败场景：构造 `used_credits=0` 的卡触发 `restore_credit` 真实抛 `HTTPException(400)`）/ `test_http_cancel_schedule_already_cancelled_fails` / `test_http_cancel_schedule_nonexistent_returns_404` / `test_http_cancel_schedule_unauthorized_fails`（学员无 `schedule:cancel` 权限 → 403）。
- `_cleanup` helper 增加按 card_id 清理 `MembershipCardTransaction` 步骤（restore_credit 成功路径会创建 txn 引用 card，删 card 前必须先删 txn，否则 FK 违反）；每步独立 session + commit，避免单步失败导致整个 session abort 阻塞后续清理。

## 3. 实施中发现的问题

| # | 问题 | 处置 |
|---|------|------|
| 1 | 首轮测试 3 failed + 1 error：清理 card 时被 `MembershipCardTransaction` 外键引用阻塞 → session abort → schedule 也未清理 → 残留数据级联导致后续用例的 `uq_bookings_schedule_student_active` 唯一约束冲突 | 修复 `_cleanup`：增加按 card_id 清理 txn 步骤；每步独立 session + commit；并改用 2 个临时 student（fixture 内 admin HTTP 创建）规避唯一约束 |
| 2 | 首轮 `test_cancel_schedule_partial_failure_rolls_back_prior_success` 用同一 student 创建 2 个 BOOKED booking 在同一 schedule 上，违反 `uq_bookings_schedule_student_active` 唯一约束 | fixture 内创建 2 个临时 student（student_a / student_b），`partial_failure` 用例改用 `student_a_id` + `student_b_id` 分别创建 booking |

## 4. 与计划的偏差

- 计划列出的 2 个文件（service.py 改动 + 新测试）全部按方案交付，无新增计划外源文件改动。
- 实施中对测试 fixture 做了 2 处工程性调整（详见第 3 节），不涉及业务代码逻辑变更。

## 5. 数据兼容与迁移

- 无 DB 结构变更，无迁移。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。
- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变；Service 签名不变 → 无需 `pnpm gen:types`，前端 4 端无影响。

## 6. 测试结果

- `test_cancel_schedule_rollback.py`：**12 passed**（3.25s）
- 回归 `test_checkin_complete_lock.py` + `test_booking_ownership.py` + `test_auth_api.py`：**44 passed**（10.76s）
- 合计 **56 passed**，无 failure / error。

详见 [runtime-test-report.md](./runtime-test-report.md)。
