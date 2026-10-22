# F6.5 发布说明：原子改期 / 原子改派

> 状态：**已交付**（2026-10-22 人工验收通过；D-6 已由 T6.5.11 修复）
> 日期：2026-10-22

## Feature

学员在单一事务内完成「改期」（换排期）或「改派」（同排期换会员卡），旧约取消、新约建立、名额迁移、卡额度回补/扣减、审计记录一次提交。

## Problem

此前无改期能力：学员只能先取消再重新预约，存在两个独立事务之间的名额与卡额度空窗（取消成功但目标已满，或旧卡已回补而新卡扣次失败），且无法追溯「取消是否因改期」。

## Fix

- 新增 `POST /api/v1/bookings/{booking_id}/reschedule`（`@require_roles("student")`，可选 `Idempotency-Key`）。
- `BookingService.reschedule_booking` 复合事务：旧约 `CANCELLED` + 新约 `BOOKED`；同排期则原地换卡，名额不变。
- 固定锁序：`pg_advisory_xact_lock(tenant, student)` → booking 行 → 排期 `id ASC` → 学员卡集 `id ASC`；写入阶段异常整体回滚。
- 复用 F6.4 时间段重叠校验并新增 `exclude_booking_id` 排除自身。
- 新增审计表 `booking_reschedules`：记录新旧 booking / 排期 / 卡、操作类型、幂等键；两个部分唯一索引兜底。
- 次卡同卡执行「回补再扣」；期卡/无限卡回补 no-op；期卡 PENDING 按剩余预约 + 新约重算锚点，不改写有效期。
- 并发修复：`get_by_id_for_update`、`get_by_ids_for_update` 增加 `populate_existing=True`，避免 identity map 旧快照导致丢更新/超卖/双重回补。
- **D-6 修复（T6.5.11）**：`cancel_schedule` 改为 `booking(id ASC) FOR UPDATE` → `schedule FOR UPDATE` → 持锁后重新收集并过滤 `BOOKED` 预约，与改期共用同一锁序，消除重复回补、新约逃逸与改期落入已取消排期的窗口。

## Files Changed

- `apps/api/src/app/modules/booking/models.py`
- `apps/api/src/app/modules/booking/repository.py`
- `apps/api/src/app/modules/booking/service.py`
- `apps/api/src/app/modules/booking/schemas.py`
- `apps/api/src/app/modules/booking/router.py`
- `apps/api/src/app/modules/schedule/repository.py`
- `apps/api/src/app/modules/schedule/service.py`（改期主链路 + T6.5.11 排期取消锁硬化）
- `apps/api/src/app/modules/membership/service.py`
- `apps/api/alembic/versions/f6a5b4c3d2e1_add_booking_reschedules.py`（新增）
- `apps/api/tests/integration/test_booking_reschedule.py`（新增）
- `apps/api/tests/integration/test_booking_reschedule_concurrency.py`（新增）
- `apps/api/tests/membership_support.py`（测试支撑）
- `packages/api-types/openapi.json`、`packages/api-types/schema.d.ts`（生成物）

## Tests

| 集合 | 结果 |
|------|------|
| 功能定向 | 31 passed |
| 并发定向 | 9 passed（D-6 两条连续 10 轮稳定） |
| 定向回归（预约/卡/排期/归属） | 93 passed（分两批执行） |
| RBAC | 17 passed |
| 租户隔离 | 3 passed / 2 failed（既有事件循环问题） |
| 静态 | `py_compile`、`ruff`、迁移往返与 `alembic check` 均通过 |

## Acceptance

- PASS：B-1~B-4、B-6~B-10、B-12、B-13、B-16~B-20；C-1~C-8；D-1~D-6、D-8、D-10（部分）；E-1~E-4、E-6。
- NOT VERIFIED：B-5、B-11 其余分支、B-14 冻结/过期/类型不适配、B-15、C-9、D-7/D-9、全量 pytest、多实例。
- **人工验收通过（2026-10-22）**：B-15、B-11 其余分支、B-14 冻结/过期/课程类型不适配经人工判定逻辑正确；D-6 已实测。

## Known Risks

1. ~~**D-F6.5-1**：排期取消链路未锁 booking~~ —— **已关闭**（T6.5.11 锁硬化，D-6 两条用例 PASS）。
2. **D-F6.5-2**：期卡 PENDING 锚点可能漂移，旧 PENDING 卡可能永久失去锚点（B-5 未单测，人工已接受）。
3. **D-F6.5-3**：审计表无业务 FK，排期/预约硬删后可能产生孤儿引用。
4. **D-F6.5-4**：目标排期校验规则与 `create_booking` 重复，存在漂移风险。
5. **D-F6.5-5**：D-10 跨 booking 同幂等键与两个约束 409 分支未覆盖。
6. 全量 `pytest`、生产多实例行为未验证。

## Migration / Rollback

- 迁移：`f6a5b4c3d2e1`（down_revision `a7b8c9d0e1f2`）；已实测 `upgrade` / `downgrade -1` 往返。
- 代码回滚：新端点纯新增，回滚后旧接口不受影响。
- 数据回滚：**不自动回滚**已完成改期；需人工按 `booking_reschedules` 定位后补偿，禁止脚本批量反向改期。

## Release Notes

- 兼容变更：新增端点与响应 DTO，不改既有字段；4 端现有调用不受影响。
- 前端接入：student-web（F6.10）、miniapp（F6.11）；写操作需二次确认，401 交既有 API 层刷新重放。
- 上线观察：改期成功率、409 重放占比、`booking_reschedules` 增长量、锁等待时长。
