# F2.3 — Release Note

## 签到/完成加行锁（2026-09-28）

### 功能变更

- `POST /api/v1/bookings/{booking_id}/check-in`（签到）：Service 内取 booking 由普通 `SELECT` 改为 `SELECT ... FOR UPDATE` 行锁。并发签到请求被序列化：第一个成功（BOOKED → CHECKED_IN），第二个拿到锁后重新检查 status 已是 CHECKED_IN → 返回 400「当前预约状态无法签到」。消除"同一预约被签到两次"的 TOCTOU 竞态。
- `POST /api/v1/bookings/{booking_id}/complete`（完成课程）：同上改为行锁。并发完成请求被序列化：第一个成功（BOOKED/CHECKED_IN → COMPLETED），第二个返回 400「当前预约状态无法完成」。消除"同一预约被完成两次"的竞态。
- 两处实现与既有 `cancel_booking`（`_do_cancel_booking` 已用 `get_by_id_for_update`）同构，统一 booking 模块的并发安全模型。

### 兼容性

- API 路径、方法、请求体、响应模型全部不变；Service 签名 `check_in_booking(db, booking_id)` / `complete_booking(db, booking_id)` 不变 → 无需 `pnpm gen:types`。
- 响应字段集合不变（仍返回 `BookingResponse`）。
- 前端 4 端影响评估：
  - admin-web：签到/完成端点契约不变，仅并发行为更安全 → **不涉及**
  - teacher-web：同上 → **不涉及**
  - student-web：不消费 check-in/complete 端点 → **不涉及**
  - miniapp：不消费 check-in/complete 端点 → **不涉及**

### 修复

- 修复 `check_in_booking` 无行锁导致的并发双签到竞态（[service.py:283](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L283) `get_by_id` → `get_by_id_for_update`）。
- 修复 `complete_booking` 无行锁导致的并发双完成竞态（[service.py:307](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L307) 同上）。

### 运维与数据

- 无数据库结构变更，无需迁移（FOR UPDATE 按主键 `bookings.id` 命中，已有主键索引）。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。
- 行锁开销：按主键行锁，不锁表；不同 booking 间无锁竞争；正常单请求仅 SELECT 多 `FOR UPDATE` 子句，额外开销可忽略。

### 已知遗留（后续处理）

- `check_in` / `complete` 端点目前仅 `booking:manage` 权限校验，未做"教师只能对自己排期下的预约签到/完成"的归属校验——属另一 Feature 范围（写操作归属校验债务项，F2.2 review 已提出）。
- `complete_booking` 当前未触发课时扣减/积分发放（仅状态流转）；未来若 `complete` 接入扣次，本 Feature 的行锁已是必要前置保障。
