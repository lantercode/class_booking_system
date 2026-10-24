# F2.4 — Release Note

## cancel_schedule 回补失败回滚（2026-09-28）

### 功能变更

- `POST /api/v1/schedules/{schedule_id}/cancel`（取消排期）：Service 内 `cancel_schedule` 方法事务模型重构——移除外层 `try/except`（吞异常导致脏提交），任一 booking 处理失败（含 `MembershipCardService.restore_credit` 失败）都直接 raise `BusinessException(500, "会员卡恢复次数失败，取消排期操作已撤销: ...")` → `db.commit()` 永不执行 → AsyncSession 被动回滚 → 全部 booking 状态变更、`decrement_booked_count`、schedule 状态变更一并回滚。消除"取消排期时某学员课时回补失败导致脏数据"的不一致。
- 实现与既有 `BookingService._do_cancel_booking`（单预约取消，restore 失败已 raise + 回滚）同构，统一 schedule / booking 模块的事务边界模型。
- 返回 dict 字段集合不变（`schedule_id` / `total_bookings` / `success_count` / `failed_count` / `failed_bookings`）；正常路径下 `success_count == total_bookings`，`failed_count == 0`，`failed_bookings == []`；事务回滚路径不到达 return → 前端不会看到"部分失败"的响应。

### 兼容性

- API 路径、方法、请求体（`ScheduleCancel{cancel_reason}`）、响应模型全部不变；Service 签名 `cancel_schedule(db, schedule_id, cancel_reason, operator_id) -> dict[str, Any]` 不变 → 无需 `pnpm gen:types`。
- 返回 dict 字段集合不变 → router L192-193 仍可消费 `total_bookings` / `success_count` 构造 msg。
- 前端 4 端影响评估：
  - admin-web：取消排期端点契约不变，仅事务语义更安全（失败回滚而非脏提交）→ **不涉及**
  - teacher-web：同上 → **不涉及**
  - student-web：不消费 `cancel_schedule` 端点（学员通过 `POST /bookings/{id}/cancel` 或 `POST /bookings/cancel-by-schedule` 取消单预约）→ **不涉及**
  - miniapp：同上 → **不涉及**

### 修复

- 修复 `cancel_schedule` 外层 try/except 吞异常导致脏提交的数据不一致：
  - 修复前：restore_credit 失败 → 外层 except 接住 → `failed_bookings.append(...)` → 循环继续 → `db.commit()` 提交已变更的 booking.status=CANCELLED、booked_count 已减、但 credit 未恢复 → 学员卡被"白扣 1 次"。
  - 修复后：restore_credit 失败 → 内层 except 包装为 `BusinessException(500)` → raise 传播出方法 → `db.commit()` 永不执行 → AsyncSession ROLLBACK → 一切回到初始状态，运营可重试取消或排查 card 异常原因。

### 运维与数据

- 无数据库结构变更，无需 migration（`decrement_booked_count` 与 `get_card_with_lock` 的 `with_for_update` 按主键命中，已有主键索引）。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。
- 行锁开销：按主键行锁，不锁表；不同 schedule 间无锁竞争；正常单请求仅 SELECT 多 `FOR UPDATE` 子句，额外开销可忽略。

### 已知遗留（后续处理）

- `cancel_schedule` 当前 `page_size=1000` 上限：单排期 BOOKED 预约数超过 1000 时会漏处理。实际排期容量通常远小于 1000，属另一优化 Feature 范围。
- `cancel_schedule` 当前仅取消 `status=BOOKED` 的预约，对 CHECKED_IN / COMPLETED 预约不特殊处理。建议后续 Feature 复核"取消排期对 CHECKED_IN 预约的处置策略"。
- `cancel_schedule` 与 `_do_cancel_booking` 都未做"取消后通知学员"，属 F6.2 通知系统范围。
