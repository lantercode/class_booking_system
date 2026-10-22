# F6.5 运行时测试报告

> 日期：2026-10-22
> 环境：macOS · Python 3.12（`apps/api/.venv`）· 本地 PostgreSQL 15 · 本地 Redis · 真实 Uvicorn（8765）
> 结论：定向功能 31 + 并发 9（含 D-6 两条）全部通过；定向回归 93（含 RBAC 17）通过；`test_tenant_isolation.py` 2 例因**既有**事件循环问题失败（与本 Feature 无关）。
> 未覆盖项集中列于 §5，不得视为 PASS。

## 1. 执行命令与结果

```bash
cd apps/api
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_reschedule.py -q
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_reschedule_concurrency.py -q
```

| 集合 | 结果 |
|------|------|
| 功能 `test_booking_reschedule.py` | **31 passed** |
| 并发 `test_booking_reschedule_concurrency.py` | **9 passed**（D-1~D-6、D-8、D-10）；并发快照修复后连续 6 轮全通过；D-6 新增用例连续 **10 轮**稳定 |

定点回归：

| 集合 | 文件数 | 结果 |
|------|--------|------|
| 归属（session 级 fixture，单独执行） | 1 | **10 passed** |
| F6.3 / F6.4 / 预约主链路 / 排期 / RBAC | 10 | **83 passed**（含 RBAC 17） |
| 租户隔离（既有用例） | 1 | 3 passed / **2 failed**（`attached to a different loop`，既有问题） |

> 回归分两批执行：`test_booking_ownership.py` 的 `booking_data` 为 session 级 fixture，与后续用例同会话运行时其 `now+3d` 预约会触发既有时间重叠校验（与本 Feature 无关），因此单独成批；两批合计 93 passed，与历史口径一致。

## 2. 功能与权限（B / C）

| AC | 用例 | 结果 |
|----|------|------|
| B-1 次卡同卡改期 | `test_b1_count_card_same_card_reschedule` | PASS |
| B-2 次卡异卡改期 | `test_b2_count_card_cross_card_reschedule` | PASS |
| B-3 期卡 ACTIVE 同卡改期 | `test_b3_period_active_reschedule_keeps_validity` | PASS |
| B-4 期卡 PENDING 改期重算锚点 | `test_b4_period_pending_reschedule_reanchors` | PASS |
| B-5 PENDING 期卡→另一 PENDING 期卡 | — | **NOT VERIFIED** |
| B-6 纯改派 | `test_b6_pure_card_swap` | PASS |
| B-7 同排期同卡 | `test_failure_same_schedule_same_card` | PASS |
| B-8 目标排期已满 | `test_failure_target_full` | PASS |
| B-9 与其他预约时间重叠 | `test_failure_overlap_with_other_booking` | PASS |
| B-10 与旧约自身重叠（排除自身） | `test_boundary_touching_target_allowed` | PASS |
| B-11 目标排期不可用 | `test_failure_target_cancelled`（仅 CANCELLED） | **部分 PASS**：其余状态分支未单测 |
| B-12 旧约非 BOOKED | `test_failure_non_booked_status`（CHECKED_IN/COMPLETED/NO_SHOW/CANCELLED 4 参数） | PASS |
| B-13 取消窗口 | `test_failure_cancel_window` | PASS |
| B-14 目标卡异常（冻结/过期/类型不适配） | C-6 他人卡 403、C-7 跨租户卡 404 | **部分 PASS**：冻结/过期/课程类型未单测 |
| B-15 目标次卡余额 0 | — | **NOT VERIFIED** |
| B-16 无卡预约附加新卡 | `test_failure_no_card_booking_cannot_attach_card` | PASS |
| B-17 无卡改期保持无卡 | `test_no_card_booking_reschedule_keeps_no_card` | PASS |
| B-18 扣次失败整体回滚 | `test_b18_rollback_when_target_card_deduct_fails` | PASS |
| B-19 幂等重放 | `test_b19_idempotency_key_replay`、`test_b19_replay_without_key_uses_audit` | PASS |
| B-20 同键不同参数 409 | `test_b20_same_key_different_params_conflict` | PASS |
| C-1 未登录 401 | `test_c1_unauthenticated_returns_401` | PASS |
| C-2 teacher 403 | `test_c2_teacher_forbidden` | PASS |
| C-3 admin 403 | `test_c3_admin_forbidden` | PASS |
| C-4 改他人预约 403 | `test_c4_non_owner_forbidden` | PASS |
| C-5 跨租户 booking 404 | `test_c5_cross_tenant_booking_returns_404` | PASS |
| C-6 他人卡 403 | `test_c6_other_student_card_forbidden` | PASS |
| C-7 跨租户卡 404 | `test_c7_cross_tenant_card_returns_404` | PASS |
| C-8 伪造身份字段被忽略 | `test_c8_forged_identity_fields_ignored` | PASS |
| C-9 审计表跨租户查询 | 无查询端点/用例 | **NOT VERIFIED**（Repository 继承 `TenantAwareRepository`，仅静态依据） |

## 3. 并发与幂等（D）

| AC | 用例 | 结果 |
|----|------|------|
| D-1 同 booking 并发两个目标 | `test_d1_same_booking_two_targets_only_one_succeeds` | PASS |
| D-2 同学员两个 booking 并发改期 | `test_d2_same_student_two_bookings_two_targets` | PASS |
| D-3 创建 vs 改期 | `test_d3_same_student_create_vs_reschedule` | PASS |
| D-3 补充：跨学员抢最后名额 | `test_d3_extra_last_seat_cross_student_only_one_wins` | PASS |
| D-4 反向改期无死锁 | `test_d4_reverse_reschedule_no_deadlock` | PASS |
| D-5 改期 vs 取消 | `test_d5_reschedule_vs_cancel_same_booking` | PASS |
| D-6 改期 vs 排期取消 | `test_d6_reschedule_vs_schedule_cancel_no_double_restore`、`test_d6_reschedule_into_cancelled_schedule_no_orphan` | **PASS**：仅 1 次回补；取消后的排期无残留 BOOKED；连续 10 轮稳定 |
| D-7 改期 vs 签到/完成 | — | **NOT VERIFIED**（依赖同 booking 行锁，静态推断安全） |
| D-8 事务失败注入 | B-18 覆盖「回补后扣次失败」全回滚 | PASS（间接） |
| D-9 对新 booking 二次改期 | — | **NOT VERIFIED** |
| D-10 幂等键并发冲突 | `test_d10_same_idempotency_key_concurrent_replay` | **部分 PASS**：覆盖同 booking 并发重放；acceptance 所指「不同 booking 同 key」与两个 `IntegrityError → 409` 分支未覆盖 |

> 首轮失败的三条（反向改期丢更新、跨学员超卖、改期 vs 取消双重回补）均由 `populate_existing=True` 修复；修复后连续 6 轮无抖动。
>
> **D-6 修复（T6.5.11）**：`cancel_schedule` 改为 `booking(id ASC) FOR UPDATE` → `schedule FOR UPDATE` → 持锁后重收集并过滤 BOOKED，消除「重复回补 / 新约逃逸 / 改期落入已取消排期」。两条用例覆盖 S→T 与 T→S 两个并发方向，均 PASS。

## 4. 回归（E）

| AC | 结果 | 证据 |
|----|------|------|
| E-1 创建/取消/签到/完成/归属 | PASS | `test_booking_card_authorization.py`、`test_booking_ownership.py`、`test_checkin_complete_lock.py` |
| E-2 F6.3 卡状态机/扣次/期卡 | PASS | `test_membership_card_deduct_lifecycle.py`、`test_membership_period_card_lifecycle.py`、`test_period_card_activation_concurrency.py` |
| E-3 F6.4 时间段重叠 | PASS | `test_booking_time_overlap.py` |
| E-4 排期创建/取消/删除 | PASS | `test_schedule_create_concurrency.py`、`test_cancel_schedule_rollback.py`、`test_delete_schedule_service.py`（取消链路锁硬化后回归通过） |
| E-5 租户隔离与 RBAC | **部分 PASS** | RBAC 17 passed；租户隔离 3 passed / 2 failed（既有 loop 问题，与本次无关） |
| E-6 OpenAPI / 类型 | PASS（生成） | 端点存在于 `openapi.json` / `schema.d.ts`；前端 TS 编译留待 F6.10/F6.11 |

## 5. NOT VERIFIED（不得视为 PASS）

| 项 | 原因 | 替代验证 |
|----|------|----------|
| B-5 | 未构造「两张 PENDING 期卡互改」数据集 | 代码审查：`_validate_period_anchor_if_needed` 不写有效期 |
| B-11 其余分支 | 仅测 CANCELLED | `_validate_target_schedule` 与 `create_booking` 同规则，回归集覆盖创建侧 |
| B-14 冻结/过期/类型不适配 | 未单测 | 复用 F6.3 `validate_card_for_booking`，回归 48 passed |
| B-15 余额 0 异卡 | 未单测 | B-18 已覆盖扣次失败回滚路径 |
| C-9 | 审计表无对外查询接口 | Repository 继承 `TenantAwareRepository`（静态） |
| D-7 / D-9 | 未构造并发/连续改期用例 | D-7 依赖同 booking 行锁；D-9 依赖旧约状态判定 |
| 全量 pytest | 基线组未执行 | 定向 40 + 回归 93 + 租户隔离 5 = 138 例 |
| 多实例 / 生产 PostgreSQL | 本地单实例 | 锁为 DB 级，理论有效 |

## 6. 复现命令

```bash
pnpm db:up
cd apps/api
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/integration/test_booking_reschedule.py \
  tests/integration/test_booking_reschedule_concurrency.py -q
```
