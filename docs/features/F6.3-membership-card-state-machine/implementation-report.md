# F6.3 实施报告（Implementation Report）

> 日期：2026-10-22
> 范围：后端（membership / booking / schedule）+ 1 个数据库迁移
> 结论：**实现完成，测试通过（后端范围）**；全量套件、四端联调、生产数据未验证。

## 1. 落地内容

| 任务 | 实现结果 |
|------|---------|
| T6.3.1 发卡 | period 卡强制 `PENDING`，`valid_from/expire_at` 留空，写入 `validity_days` 快照；count/unlimited 行为不变 |
| T6.3.2 预约校验 | PENDING 期卡（`valid_from IS NULL`）可预约、不扣次；按「最早非取消预约排期日 + validity_days」计算预期窗口并做区间重叠预校验；次卡改为按**排期日**校验有效期并预扣 |
| T6.3.3 激活 | 首次 `COMPLETED` / `NO_SHOW` 激活：锁学员卡集（id ASC）→ 状态重检 → 幂等键 `booking_{id}_period_activate` → 写 ACTIVE + 有效期 + ISSUE 流水 |
| T6.3.4 收口 | `schedule/scheduler.py` 不再 bulk 写预约状态，改由 `BookingService.finalize_schedule_bookings` 处理并触发激活 |
| T6.3.5 回补 | `restore_credit` 对 period/unlimited 在锁后 no-op；次卡回补不变 |
| T6.3.6 生命周期任务 | `freeze_card` 拒绝 PENDING；过期扫描扩展为 `ACTIVE/PENDING + expire_at IS NOT NULL`；新增 PENDING 超 90 天（按 `created_at`）作废任务，已使用卡跳过 |
| T6.3.7 测试 | 新增 1 个单测 + 7 个集成测试文件，共 41 条用例 |

## 2. 文件级变更

| 文件 | 变更 |
|------|------|
| `apps/api/src/app/modules/membership/models.py` | 新增 `validity_days`（Integer, nullable） |
| `apps/api/alembic/versions/a7b8c9d0e1f2_add_membership_card_validity_days.py` | 加列 + 幂等回填（产品优先、日期差兜底） |
| `apps/api/src/app/modules/membership/service.py` | 卡集锁（`FOR NO KEY UPDATE` + `populate_existing`）、预约校验、激活、过期/作废 |
| `apps/api/src/app/modules/membership/repository.py` | 卡集行锁查询 |
| `apps/api/src/app/modules/membership/scheduler.py` | 过期扫描扩展、PENDING 90 天作废任务 |
| `apps/api/src/app/modules/booking/service.py` | 预约校验/扣次分支、完成激活、排期 finalize 收口、锚点修复 |
| `apps/api/src/app/modules/booking/repository.py` | `exists_card_booking_with_statuses`、`get_earliest_card_booking_start` |
| `apps/api/src/app/modules/schedule/scheduler.py` | 终态处理改为调用 BookingService |
| `apps/api/src/app/modules/schedule/service.py` | 取消排期链路适配新的回补语义 |
| `apps/api/src/app/core/config.py` | `PENDING_CARD_CANCEL_ENABLED`、`PENDING_CARD_CANCEL_DAYS` |
| `apps/api/src/app/main.py` | 注册 PENDING 作废定时任务（1440 min） |

测试文件：`tests/membership_support.py`、`tests/unit/test_membership_card_state_machine.py`、`tests/integration/test_membership_period_card_lifecycle.py`、`test_period_card_booking_validation.py`、`test_period_card_activation_concurrency.py`、`test_membership_card_deduct_lifecycle.py`、`test_booking_card_concurrency.py`、`test_membership_card_expiry_jobs.py`、`test_booking_card_authorization.py`。

## 3. 实施中发现并修复的问题

1. **并发激活锚点错误（真实缺陷）**：原实现用"当前完成预约的排期日"作为生效日，并发完成两张预约时可能取到较晚日期（实测 1/6 失败，日期差 1 天）。修复为统一取该卡**最早非取消预约排期日**，两处调用点（`complete_booking`、`finalize_schedule_bookings`）均改。
2. **锁等待后读到 identity map 陈旧状态**：改为 `FOR NO KEY UPDATE` + `populate_existing`，避免重复写激活流水/超扣。
3. **FK 锁升级死锁**：booking 外键的 `FOR KEY SHARE` 与后续 `FOR UPDATE` 冲突，随上条一并解决。
4. **Lint**：本次新增/修改文件存在 12 处 import 排序与空白符问题，已用 `ruff --fix` 修复并通过复检。

## 4. 与设计的偏差

| 项 | 设计 | 实现 | 原因 |
|----|------|------|------|
| 列类型 | SmallInteger | Integer | 与产品表同类型（迁移注释已说明） |
| 双卡并发冲突 | fail-closed | fail-closed（保留） | 与已确认决策一致 |

## 5. 未完成 / 不在范围

- 全量 `pytest` 未执行（仅 F6.3 定向 + 11 个回归文件）
- 四端联调、前端 PENDING 展示（F6.10/F6.11）
- 多实例 APScheduler 互斥
- 生产数据回填量与首批批量作废影响评估

## 6. 验证入口

- `docs/features/F6.3-membership-card-state-machine/static-verification.md`
- `docs/features/F6.3-membership-card-state-machine/runtime-test-report.md`
- `docs/features/F6.3-membership-card-state-machine/review.md`
