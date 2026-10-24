# F6.3 运行时测试报告（Runtime Test Report）

> 日期：2026-10-22
> 环境：macOS · Python 3.12（`apps/api/.venv`）· 本地 PostgreSQL 15 · 本地 Redis
> 结论：**F6.3 定向 41 条 + 回归 118 条通过**；全量套件、四端联调、多实例调度 **NOT VERIFIED**。

## 1. 执行命令与结果

### 1.1 F6.3 定向用例

```bash
cd apps/api
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/unit/test_membership_card_state_machine.py \
  tests/integration/test_membership_period_card_lifecycle.py \
  tests/integration/test_period_card_booking_validation.py \
  tests/integration/test_period_card_activation_concurrency.py \
  tests/integration/test_membership_card_deduct_lifecycle.py \
  tests/integration/test_booking_card_concurrency.py \
  tests/integration/test_membership_card_expiry_jobs.py \
  tests/integration/test_booking_card_authorization.py -q
```

| 阶段 | 结果 |
|------|------|
| 首次独立复跑（修复前） | 41 passed / 8.84s |
| lint 修复后首次 | **1 failed / 40 passed**（`test_concurrent_complete_activates_period_card_once`，日期差 1 天） |
| 定位根因并修复后 | 连续 8 轮：41 passed |
| 加压 10 轮 | 10/10：41 passed |
| 合计 | 修复后 23 轮中 1 轮出现 4 failed（见 1.3） |

### 1.2 回归用例

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/integration/test_checkin_complete_lock.py \
  tests/integration/test_cancel_schedule_rollback.py \
  tests/integration/test_booking_fk_membership_card.py \
  tests/integration/test_order_fk_membership_card.py \
  tests/integration/test_status_check_constraints.py \
  tests/integration/test_schedule_create_concurrency.py \
  tests/integration/test_booking_ownership.py \
  tests/integration/test_rbac_enforcement.py \
  tests/integration/test_rbac.py \
  tests/test_scheduler_tenant_isolation.py \
  tests/unit/test_unfreeze_lock_ordering.py -q
```

结果：**118 passed**（12.84s / 13.07s，两次一致）。

### 1.3 稳定性观察（如实记录）

1. **真实缺陷（已修复）**：并发完成两张预约时，期卡生效日取"先到达的完成请求"的排期日，导致约为 `first_start+1天`（1/6 复现）。修复：统一取该卡**最早非取消预约排期日**作为锚点（`booking/service.py` 两处调用点）。修复后 23 轮未再复现该日期断言失败。
2. **一次未复现异常**：某轮出现 4 failed，当轮与我的 `py_compile` 并行执行，未捕获用例名；随后 23 轮全部通过。根因 **UNKNOWN**，怀疑并发写入 `.pyc` 与测试导入竞争。已记录为风险，不声称已排除。

## 2. 验收标准（B/C/D/E）对照

### B. 运行时功能

| 行为 | 用例 | 结果 |
|------|------|------|
| 期卡发卡 PENDING 且无有效期 | `test_issue_period_card_pending_without_validity` | PASS |
| 期卡发卡必须提供 validity_days | `test_issue_period_card_requires_validity_days` | PASS |
| 次卡发卡行为不变 | `test_issue_count_card_unchanged` | PASS |
| PENDING 不可冻结 | `test_freeze_pending_rejected` | PASS |
| 完成首次激活且仅一次 | `test_manual_complete_activates_period_card_once` | PASS |
| 期卡取消不回补 | `test_period_card_cancel_no_restore` | PASS |
| 次卡预扣 + 取消回补 | `test_count_card_deduct_and_cancel_restore` | PASS |
| PENDING 期卡可预约且不扣次 | `test_pending_period_card_can_book_without_deduct` | PASS |
| 超出预期窗口拒绝 | `test_period_card_out_of_expected_window_rejected` | PASS |
| 预期窗口重叠 409 | `test_pending_period_card_overlap_conflict_409` | PASS |
| 到期日当天可约 | `test_expire_at_same_day_allowed` | PASS |
| 过期卡拒绝 | `test_expired_card_rejected` | PASS |
| 次卡按排期日校验/扣次 | `test_count_card_validity_uses_schedule_date`、`test_count_card_expired_by_schedule_date_rejected` | PASS |
| 余额不足回滚预约与名额 | `test_insufficient_credits_rolls_back_booking_and_capacity` | PASS |
| NO_SHOW 也激活 | `test_finalize_no_show_also_activates` | PASS |
| finalize 完成并激活 | `test_finalize_checked_in_completes_and_activates` | PASS |
| 过期任务覆盖 ACTIVE/PENDING | `test_expire_job_marks_active_and_pending_expired` | PASS |
| 90 天作废：旧卡作废 | `test_cancel_job_cancels_old_unused_pending_card` | PASS |
| 90 天作废：已使用跳过 | `test_cancel_job_skips_used_pending_card` | PASS |
| 90 天作废：新卡跳过 | `test_cancel_job_skips_recent_pending_card` | PASS |

### C. 权限与租户

| AC | 用例 | 结果 |
|----|------|------|
| C-1 非管理员不可发卡 | `test_issue_card_forbidden_for_non_admin` | PASS |
| C-2 非学员不可预约 | `test_booking_forbidden_for_non_student`（authorization 文件） | PASS |
| C-3 无权限不可完成 | `test_student_cannot_complete_booking` | PASS |
| C-5 他人卡不可用 | `test_other_student_card_forbidden` | PASS |
| C-6 身份不来自请求体 | 代码审查（未新增身份入参） | PASS（审查） |
| C-4 跨租户卡不可用 | 无专用用例 | **NOT VERIFIED** |
| C-7 定时任务租户隔离 | 未扩展 `test_pending_cancel_tenant_isolation` | **NOT VERIFIED** |
| C-8 租户上下文清理 | 依赖既有 `test_scheduler_tenant_isolation.py`（118 回归中通过） | PASS（间接） |

### D. 并发与幂等

| 场景 | 用例 | 结果 |
|------|------|------|
| 并发完成只激活一次 | `test_concurrent_complete_activates_period_card_once` | PASS（修复后 23 轮） |
| 并发预约不超扣 | `test_concurrent_bookings_cannot_overspend_credits` | PASS |

### E. 回归

118 passed（含签到/完成锁、取消排期回滚、FK、状态约束、排课并发、预约归属、RBAC、调度租户隔离、解冻锁序）。

## 3. NOT VERIFIED（不得视为 PASS）

| 项 | 原因 |
|----|------|
| 全量 `pytest` | 未执行（仅定向 + 11 个回归文件） |
| 四端联调 / 小程序 PENDING 展示 | 不在本次后端范围（F6.10/F6.11） |
| 跨租户卡预约（C-4） | 无用例 |
| 多实例 APScheduler 互斥 | 未实现/未验证 |
| 生产库回填与首批批量作废 | 无生产数据环境 |
| 一次 4 failed 异常 | 未复现，根因 UNKNOWN |
