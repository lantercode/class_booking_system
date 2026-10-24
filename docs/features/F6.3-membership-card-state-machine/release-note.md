# F6.3 发布说明（Release Note）

> 日期：2026-10-22
> 类型：后端业务规则变更（无对外契约变更）
> 状态：**待人工验收 / 待生产数据评估**

## 1. 功能摘要

期卡从"发卡即 ACTIVE"改为"发卡 PENDING、首次完成/缺席激活"；次卡扣次改为按**排期日**校验有效期；新增 PENDING 90 天自动作废；排期结束的预约终态处理收口到 BookingService。

## 2. 行为变更（运维/客服需知）

| 对象 | 变更前 | 变更后 |
|------|--------|--------|
| 期卡发卡 | 立即 ACTIVE + 计算有效期 | PENDING，`valid_from/expire_at` 为空，记录 `validity_days` |
| 期卡预约 | 要求 ACTIVE；`deduct_credit` 不扣次但校验 `now` | PENDING 可预约；不扣次；按预期窗口做重叠预校验 |
| 期卡取消 | `restore_credit` 报错 | 不回补，取消正常完成 |
| 期卡完成/缺席 | 不改变卡 | 首次激活并写有效期 + ISSUE 流水 |
| 次卡有效期 | 用 `now` 判断 | 用**排期日**判断（可预约未来课程） |
| 冻结 | PENDING 可冻结 | PENDING 返回 400 |
| 过期扫描 | 仅 ACTIVE | ACTIVE + PENDING（有 expire_at） |
| PENDING 清理 | 无 | 超过 90 天（按 created_at）且未使用 → CANCELLED |
| 排期结束 | Scheduler bulk 写状态 | 调用 `BookingService.finalize_schedule_bookings` |

## 3. 部署步骤

1. 备份数据库。
2. `cd apps/api && alembic upgrade head`（目标 `a7b8c9d0e1f2`）。
3. 确认配置：`PENDING_CARD_CANCEL_ENABLED=true`（默认）、`PENDING_CARD_CANCEL_DAYS=90`。
4. 重启 API（注册新定时任务，日志应出现 `auto_cancel_pending_membership_cards`）。
5. **上线前**执行存量统计（见风险 R2）：统计 `card_type='period' AND status='pending' AND created_at < now()-90d` 的卡数。

## 4. 回滚

1. `alembic downgrade -1`（删除 `validity_days`）。
2. 设置 `PENDING_CARD_CANCEL_ENABLED=false` 并重启，停止作废任务。
3. 代码回滚到上一版本。
4. 注意：已被作废的卡不会自动恢复，需要按备份人工处理。

## 5. 技术债 / 未验证

| ID | 内容 |
|----|------|
| D-F6.3-1 | 全量 `pytest` 未执行 |
| D-F6.3-2 | 多实例调度无分布式互斥 |
| D-F6.3-3 | 存量 PENDING 卡首批批量作废影响未评估 |
| D-F6.3-4 | 小程序/管理端 PENDING 展示未适配（F6.10/F6.11） |
| D-F6.3-5 | 跨租户卡预约（C-4）、任务租户隔离（C-7）缺专项用例 |

## 6. 验证证据

- `static-verification.md`：编译/lint/迁移/范围
- `runtime-test-report.md`：41 定向 + 118 回归，含并发稳定性记录
- `review.md`：独立复核结论与风险 R1–R7
- 任务遥测：`docs/engineering/task-records/20261021-F6.3-membership-card-state-machine.md`
