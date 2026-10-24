# F6.3 — 会员卡扣次与期卡激活状态机：Acceptance Criteria

- 状态：DESIGN / 未执行
- 分组：基线组（按现状完整流程执行，不启用效率优化）
- 行号基于 2026-10-22 当前工作区。
- **重要声明**：本文件不声称任何测试已执行。当前所有 AC 均为 `PLAN_NOT_RUN`；只有在实施后按“验证方式”实际执行并通过，才可改为 `PASS`，失败则改 `FAIL` 并附证据。
- 结果判定：每条 AC 必须有可复现命令、预期状态码/DB 断言/日志断言；禁止用“看起来正常”替代。
- 统一信封：`{ "code": 0, "msg": "success", "data": {...} }`；错误同时体现在 HTTP 状态码与 `code/msg`。
- 测试前置（运行时组）：PostgreSQL 可连接、Redis 可用、种子数据已初始化（`conftest.seed_test_database`）、`live_server` 可启动。

## A. 静态构建（STATIC）

| AC | 内容 | PASS 判据 | 验证方式 | 状态 |
|----|------|-----------|----------|------|
| A-1 | 应用可导入 | 命令退出码 0，无 ImportError/AttributeError | `cd apps/api && PYTHONPATH=src .venv/bin/python -c "from app.main import app"` | PLAN_NOT_RUN |
| A-2 | 改动文件语法合法 | 所有改动 `.py` 均通过编译 | 对改动文件逐个执行 `python3 -m py_compile <file>`，退出码均为 0 | PLAN_NOT_RUN |
| A-3 | 无 `ScheduleStatus.COMPLETED` | 全仓库 Python 代码零匹配 | `rg -n "ScheduleStatus\.COMPLETED" apps/api/src` 无输出 | PLAN_NOT_RUN |
| A-4 | Scheduler 不再直写业务状态 | `schedule/scheduler.py` 中无 `update(Booking)`，且无 `schedule.status = ScheduleStatus...` 赋值 | `rg -n "update\(Booking\)|schedule\.status\s*=\s*ScheduleStatus" apps/api/src/app/modules/schedule/scheduler.py` 无输出（查询条件中的 `==` 不匹配该模式） | PLAN_NOT_RUN |
| A-5 | 期卡不再走扣次 | `create_booking` 只在 count 分支调用 `deduct_credit` | 代码审查 + `rg -n "deduct_credit" apps/api/src/app/modules/booking/service.py`；确认位于 `if card.card_type == "count"` 分支 | PLAN_NOT_RUN |
| A-6 | 期卡不再走回补 | `restore_credit` 的调用方或 Service 内部对 period/unlimited no-op | 代码审查 `membership/service.py` 的 `restore_credit`；构造 period 卡调用应无 RESTORE 流水 | PLAN_NOT_RUN |
| A-7 | API 契约无破坏性变更 | OpenAPI 中既有路径/字段无删除、无类型变更；无新增公开端点（内部方法不计） | 导出变更前后 OpenAPI 并 diff；`/api/v1/bookings`、`/api/v1/membership/cards` 请求/响应字段集合不变 | PLAN_NOT_RUN |
| A-8 | 迁移可逆 | `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` 均成功 | 在测试库执行 Alembic 三段命令，退出码 0，`membership_cards.validity_days` 存在且可空 | PLAN_NOT_RUN |
| A-9 | 迁移回填可审计 | 回填后不存在“period + 非终态 + validity_days IS NULL 且 product 有值”的卡 | SQL 统计为 0；对确实无法回填的卡输出清单（允许为 0，非 0 必须记录 UNKNOWN） | PLAN_NOT_RUN |
| A-10 | 无越界改动 | 仅改动 `apps/api/src/app/modules/{membership,booking,schedule}`、`apps/api/src/app/core/config.py`、`apps/api/src/app/main.py`、`apps/api/alembic/versions/*`、`apps/api/tests/*` 与本 Feature 文档 | 与“开工基线”做 diff（不是全量 `git status`，当前工作树已有大量历史未提交改动）；不得出现前端、`.trae/**`、`.github/**`、F6.0 文档改动 | PLAN_NOT_RUN |

## B. 运行时功能（RUNTIME）

| AC | 内容 | PASS 判据 | 验证方式 | 状态 |
|----|------|-----------|----------|------|
| B-1 | 期卡发卡为 PENDING 且有效期为空 | HTTP 201；`data.status=0`、`data.valid_from=null`、`data.expire_at=null`；DB 同值；`validity_days` 快照等于发卡入参/产品值 | 新增测试 `test_membership_period_card_lifecycle.py::test_issue_period_card_pending_without_validity`；HTTP + DB 双断言 | PLAN_NOT_RUN |
| B-2 | 次卡发卡行为不变 | 次卡仍按 `valid_from` 计算 ACTIVE/PENDING 与 `expire_at`；历史断言不回归 | 同文件 `test_issue_count_card_unchanged`；对照 `membership/service.py:397-429` 的既有语义 | PLAN_NOT_RUN |
| B-3 | 期卡发卡缺 `validity_days` 拒绝 | HTTP 400，消息含“必须设置有效天数”；不落卡、不落流水 | `test_issue_period_card_requires_validity_days`；DB count 不变 | PLAN_NOT_RUN |
| B-4 | 期卡预约不扣次、不激活 | HTTP 200/201；booking.status=1、`membership_card_id` 已写入；card.status=0、`used_credits=0`；无 CONSUME 流水 | `test_period_card_booking_validation.py::test_book_period_card_no_deduct_no_activate` | PLAN_NOT_RUN |
| B-5 | 次卡预约仍预扣 | HTTP 成功；`used_credits` +1；存在 CONSUME 流水；幂等键 `booking_{id}_deduct` | 同文件 `test_book_count_card_deducts_once` | PLAN_NOT_RUN |
| B-6 | 预期有效期冲突拒绝 | HTTP 409；无 booking 落库、`booked_count` 不变、无卡流水 | 构造 ACTIVE 同课程类型卡（区间覆盖排期日），再预约；`test_expected_validity_conflict_rejected` | PLAN_NOT_RUN |
| B-7 | 预期有效期不冲突放行 | HTTP 成功；无 409 | 构造 ACTIVE 卡区间与预期区间无交集；`test_expected_validity_no_conflict_allows` | PLAN_NOT_RUN |
| B-8 | 排期日有效期边界（D4） | 排期日 = `expire_at` 当天 → 成功；排期日 = `expire_at` 次日 → 400 | `test_booking_on_expire_date_boundary`；卡 `expire_at` 设为 23:59:59，排期分别落在当天/次日 | PLAN_NOT_RUN |
| B-9 | 未到生效日的 PENDING 不可预约 | 有 `valid_from` 的未来 PENDING 卡 → 400；D9 卡（`valid_from=NULL`）→ 成功 | `test_pending_with_future_valid_from_rejected` + `test_d9_pending_bookable` | PLAN_NOT_RUN |
| B-10 | 手动完成首次激活 | HTTP 200；booking=4；card.status=1；`valid_from` = 排期日 00:00:00；`expire_at` = 排期日 + `validity_days` - 1 的 23:59:59；一条 ISSUE（change=0，幂等键 `booking_{id}_period_activate`） | `test_period_card_activation_concurrency.py::test_manual_complete_activates_once` | PLAN_NOT_RUN |
| B-11 | 自动结束的 COMPLETED 激活 | 排期 `end_at+grace<now` 且 NORMAL；CHECKED_IN 预约 → COMPLETED；期卡 ACTIVE 且日期按排期日计算 | `test_membership_card_expiry_jobs.py::test_auto_finish_activates_period_card`；直接调用 finalize 或 job | PLAN_NOT_RUN |
| B-12 | 自动结束的 NO_SHOW 激活（D5） | BOOKED 预约 → NO_SHOW；期卡首次激活成功；次卡无额外扣次 | 同文件 `test_auto_finish_no_show_activates_period_card` | PLAN_NOT_RUN |
| B-13 | 次卡完成/缺席不重复扣 | 完成前 `used_credits=n`，完成后仍为 n；无新增 CONSUME/RESTORE | `test_count_card_complete_no_extra_deduct` | PLAN_NOT_RUN |
| B-14 | 期卡取消不激活、不回补 | 取消预约成功；card.status=0、`valid_from/expire_at` 仍 NULL；无 RESTORE 流水；不返回 400/500 | `test_period_card_cancel_no_restore` | PLAN_NOT_RUN |
| B-15 | 期卡/次卡取消排期分支 | BOOKED + period → 取消成功、卡不变；BOOKED + count → 回补 1 次 | `test_cancel_schedule_period_noop_count_restore` | PLAN_NOT_RUN |
| B-16 | PENDING 不可冻结 | HTTP 400，消息含“未激活卡不可冻结”；`frozen_until/frozen_at` 仍空；`expire_at` 不变 | `test_freeze_pending_rejected` | PLAN_NOT_RUN |
| B-17 | 过期扫描覆盖 PENDING | 构造 `status=PENDING AND expire_at<now` 的卡；任务后 status=2；次卡剩余清零；期卡写 EXPIRE（change=0） | `test_membership_card_expiry_jobs.py::test_expire_scan_includes_pending` | PLAN_NOT_RUN |
| B-18 | 90 天 PENDING 作废 | 构造 `created_at=now-91d` 的 period PENDING 卡；任务后 status=6、`cancelled_reason` 含“90”；无完成 booking 时才作废 | 同文件 `test_pending_period_card_cancelled_after_90_days` | PLAN_NOT_RUN |
| B-19 | 有完成记录的 PENDING 不误作废 | 构造 PENDING + COMPLETED booking + `created_at=now-91d`；任务后仍 PENDING | 同文件 `test_pending_with_completed_booking_not_cancelled` | PLAN_NOT_RUN |
| B-20 | 重复完成保持既有语义 | 已完成预约再次 complete → HTTP 400，消息“当前预约状态无法完成”；卡不重复激活 | 复用/扩展 `test_checkin_complete_lock.py`；或新文件 `test_period_card_activation_concurrency.py::test_repeat_complete_rejected` | PLAN_NOT_RUN |
| B-21 | 期卡缺 `validity_days` 时激活失败可见 | HTTP 400/500 且 booking 未变 COMPLETED；日志含 card_id；无半状态 | `test_period_card_missing_validity_days_fails_closed` | PLAN_NOT_RUN |
| B-22 | 期卡预约课程适用性 | 课程类型不匹配 → 400；`applicable_course_ids` 不含该课程 → 400；匹配 → 成功 | `test_period_card_course_applicability` | PLAN_NOT_RUN |
| B-23 | 同一 PENDING 期卡的预约窗口一致性 | 卡 `validity_days=7`：先约 D 日成功；再约 D+6 日成功；再约 D+7 日 → 400 “超出有效期窗口” | `test_period_card_booking_window_anchor`；按锚点=最早非取消预约排期日 | PLAN_NOT_RUN |

## C. 权限与租户（PERMISSION / TENANT）

| AC | 内容 | PASS 判据 | 验证方式 | 状态 |
|----|------|-----------|----------|------|
| C-1 | 非管理员不可发卡 | student/teacher 调用 `POST /membership/cards` → 403，Service 未被调用（无卡落库） | `test_membership_period_card_lifecycle.py::test_issue_card_forbidden_for_non_admin`；用 student token | PLAN_NOT_RUN |
| C-2 | 非学员不可预约 | admin/teacher 调 `POST /bookings` → 403 | `test_period_card_booking_validation.py::test_booking_forbidden_for_non_student` | PLAN_NOT_RUN |
| C-3 | 无 `booking:manage` 不可完成 | student token 调 complete → 403 | 既有 RBAC 测试扩展或新用例 `test_complete_forbidden_without_permission` | PLAN_NOT_RUN |
| C-4 | 跨租户卡不可用 | 租户 A 的卡在租户 B 预约 → 404/403；无 booking、无流水、无跨租户写入 | 双租户夹具；`test_cross_tenant_card_rejected` | PLAN_NOT_RUN |
| C-5 | 他人卡不可用 | 同租户 student_b 使用 student_a 的卡 → 403；错误信息不回显卡号 | `test_other_student_card_rejected` | PLAN_NOT_RUN |
| C-6 | 身份不来自请求体 | 预约请求体无 `tenant_id`/`student_id`；发卡请求的 `student_id` 仅 admin/super_admin 可用；租户只取认证上下文 | OpenAPI 检查 + 代码审查 `booking/schemas.py:12-17`、`membership/schemas.py:114-157`、`membership/router.py:178-205` | PLAN_NOT_RUN |
| C-7 | 定时任务租户隔离 | 两租户各有一张待处理卡；任务只改本租户卡；日志含 tenant_id | `test_scheduler_tenant_isolation.py` 扩展 `test_pending_cancel_tenant_isolation` | PLAN_NOT_RUN |
| C-8 | 租户上下文清理 | 任务结束 `set_tenant_id(None)`；后续查询不串租户 | 代码审查 + 任务后查询另一租户数据断言 | PLAN_NOT_RUN |

## D. 并发与幂等（CONCURRENCY / IDEMPOTENCY）

| AC | 内容 | PASS 判据 | 验证方式 | 状态 |
|----|------|-----------|----------|------|
| D-1 | 并发完成只激活一次 | 两个并发 complete：一个 200、一个 400；card ACTIVE；ISSUE 流水仅 1 条 | `test_period_card_activation_concurrency.py::test_concurrent_complete_activates_once`；`asyncio.gather` + live_server | PLAN_NOT_RUN |
| D-2 | 并发 finalize 不重复处理 | 两个并发 finalize 同一排期：只有一个提交；booking 终态与卡激活只发生一次 | `test_concurrent_finalize_idempotent` | PLAN_NOT_RUN |
| D-3 | 并发取消只成功一次 | 两个并发 cancel：一个 200、一个 400；`booked_count` 只减 1；count 卡只回补 1 次 | 复用 `test_cancel_schedule_rollback` 结构并新增 `test_concurrent_cancel_once` | PLAN_NOT_RUN |
| D-4 | 并发扣次不超扣 | 余额 1 的次卡并发两笔预约：一成一败；`used_credits` 不超过 `total_credits` | `test_concurrent_deduct_no_overdraft` | PLAN_NOT_RUN |
| D-5 | 激活幂等键生效 | 同一 `booking_{id}_period_activate` 重复调用：不新增流水；返回既有卡 | `test_activation_idempotency_key` | PLAN_NOT_RUN |
| D-6 | 定时任务重复运行幂等 | 连续执行两次 auto_finish/auto_expire/pending_cancel：第二次零业务变更（流水数、状态不变） | `test_membership_card_expiry_jobs.py::test_jobs_idempotent_on_second_run` | PLAN_NOT_RUN |
| D-7 | 激活冲突 fail-closed | 构造两张 PENDING 期卡竞争同一课程类型；第二张激活时冲突 → booking 不被置 COMPLETED、card 仍 PENDING、事务回滚 | `test_activation_conflict_rolls_back`；需先确认 UNKNOWN-1 | PLAN_NOT_RUN |
| D-8 | 锁顺序无死锁 | 并发 complete + cancel + finalize 连续 20 轮无 `deadlock detected`；无 500 | `test_lock_order_no_deadlock`；捕获日志关键字 | PLAN_NOT_RUN |
| D-9 | 卡集锁串行化期卡预约 | 同一学员并发两笔期卡预约（不同排期、同一 ACTIVE 冲突卡）：至多一笔通过冲突校验 | `test_concurrent_period_booking_serialized` | PLAN_NOT_RUN |

## E. 回归（REGRESSION）

| AC | 内容 | PASS 判据 | 验证方式 | 状态 |
|----|------|-----------|----------|------|
| E-1 | F2.3 签到/完成锁 | 全部通过；重复完成仍 400“无法完成” | `cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_checkin_complete_lock.py -v` | PLAN_NOT_RUN |
| E-2 | F2.4 取消排期回滚 | 全部通过；restore 失败整体回滚 | `pytest tests/integration/test_cancel_schedule_rollback.py -v` | PLAN_NOT_RUN |
| E-3 | F4.1 booking→card FK | 全部通过；删卡后 booking.membership_card_id 为 NULL | `pytest tests/integration/test_booking_fk_membership_card.py -v` | PLAN_NOT_RUN |
| E-4 | F4.2 order→card FK | 全部通过（卡删除不影响订单历史） | `pytest tests/integration/test_order_fk_membership_card.py -v` | PLAN_NOT_RUN |
| E-5 | F4.4 状态 Check 约束 | 全部通过；卡状态仍只允许 0/1/2/3/6 | `pytest tests/integration/test_status_check_constraints.py -v` | PLAN_NOT_RUN |
| E-6 | F4.5 排期创建并发 | 全部通过 | `pytest tests/integration/test_schedule_create_concurrency.py -v` | PLAN_NOT_RUN |
| E-7 | 预约归属 | 全部通过；不能取消他人预约 | `pytest tests/integration/test_booking_ownership.py -v` | PLAN_NOT_RUN |
| E-8 | RBAC | 全部通过 | `pytest tests/integration/test_rbac_enforcement.py tests/integration/test_rbac.py -v` | PLAN_NOT_RUN |
| E-9 | 租户隔离 | 既有用例结果与基线一致；不得因本 Feature 新增失败 | `pytest tests/integration/test_tenant_isolation.py -v`（该套件存在既有失败时，必须记录基线对比，不得声称全绿） | PLAN_NOT_RUN |
| E-10 | 定时任务租户隔离 | 全部通过 | `pytest tests/test_scheduler_tenant_isolation.py -v` | PLAN_NOT_RUN |
| E-11 | 冻结/解冻锁顺序 | 全部通过 | `pytest tests/unit/test_unfreeze_lock_ordering.py -v` | PLAN_NOT_RUN |
| E-12 | 认证回归 | 全部通过 | `pytest tests/integration/test_auth_api.py -v` | PLAN_NOT_RUN |

## F. 验收记录模板

实施完成后必须填写，禁止预填 PASS：

| AC 组 | 执行人 | 执行时间 | 命令/环境 | 结果（PASS/FAIL） | 证据（日志/报告路径） |
|-------|--------|----------|-----------|-------------------|------------------------|
| A |  |  |  | PLAN_NOT_RUN |  |
| B |  |  |  | PLAN_NOT_RUN |  |
| C |  |  |  | PLAN_NOT_RUN |  |
| D |  |  |  | PLAN_NOT_RUN |  |
| E |  |  |  | PLAN_NOT_RUN |  |

## G. 不通过时的处理

1. 任一 AC 为 FAIL，Feature 不得进入 Review/交付。
2. FAIL 必须附：复现步骤、实际 HTTP/DB 结果、期望结果、日志片段（脱敏）。
3. 若失败由既有技术债导致（如 `test_tenant_isolation.py` 预存失败），必须在结果中给出“基线失败清单 vs 本次失败清单”，不得混为一谈。
