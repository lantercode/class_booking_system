# F2.3 — 签到/完成加行锁 · 需求文档

> Feature ID：F2.3
> 作者：backend-engineer
> 日期：2026-09-28
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（纯后端任务，走 v2 轨道，不召前端；不触 DB 结构 → 不召 database-engineer 改库，仅复用既有 Repository 方法）
> 依赖：无（`get_by_id_for_update` 已存在于 [repository.py:202-224](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L202-224)）
> 前置 Feature：F2.2（预约归属，已完成；本 Feature 不依赖其结果，但共用 booking 模块）

---

## Goal

`check_in_booking` / `complete_booking` 两个写操作在并发请求下保证状态机一致性：同一 booking 的两个并发签到（或两个并发完成）请求，有且仅有一个成功，另一个被业务异常拒绝（"当前预约状态无法签到/完成"）。通过既有 `SELECT ... FOR UPDATE` 行锁实现，不引入新基础设施。

## User Story

作为管理员/教师（`booking:manage` 权限），
我希望对同一学员的预约进行签到/完成操作时，即使因网络重试或前端误触导致两个并发请求同时到达，也只会有一次签到/完成生效，
以便：

- 不会出现"同一预约被签到两次"导致的状态错乱（最终态仍是 `CHECKED_IN`，看似无害，但日志/审计重复、`checked_in_at` 被覆盖、可能的下游扣次/积分重复）。
- 不会出现"同一预约被完成两次"导致的重复完成（`COMPLETED` 是终态，重复完成虽不致状态倒退，但属于无效写操作，且未来若 `complete` 触发课时扣减/积分发放时会被重复触发）。

作为系统，
我希望签到/完成的状态流转与已有的 `cancel_booking`（`_do_cancel_booking` 已用 `get_by_id_for_update` + 拿锁后重检 status）保持同构，以便并发安全模型统一、可审计、可维护。

## Background / 现状（已核查的代码事实）

| 事实 | 证据 |
|------|------|
| `check_in_booking` 无行锁 | [service.py:275-297](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L275-297)：`booking = await self.repo.get_by_id(db, booking_id)` → 读到 `BOOKED` 后直接 `booking.status = CHECKED_IN` → commit。两个并发签到请求可同时读到 `BOOKED`，同时写入 `CHECKED_IN` |
| `complete_booking` 无行锁 | [service.py:299-320](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L299-320)：同模式，`get_by_id` → 读到 `BOOKED`/`CHECKED_IN` → 直接写 `COMPLETED` → commit。两个并发完成请求可同时通过 status 检查 |
| 既有 `get_by_id_for_update` 已含租户过滤 | [repository.py:202-224](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L202-224)：`select(Booking).where(Booking.id == booking_id).with_for_update()` + `tenant_id` 条件；不用 `skip_locked`（注释说明取消操作应排队序列化） |
| `cancel_booking` 已是同构锁模式 | [service.py:199-273](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L199-273) `_do_cancel_booking`：开头 `get_by_id_for_update` → 拿锁后重检 status → 后续全用 `locked_booking`。本 Feature 让 check_in/complete 与之对齐 |
| 端点装饰器不变 | [router.py:189-220](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/router.py#L189-220)：`POST /{booking_id}/check-in` 与 `POST /{booking_id}/complete` 均为 `@require_permissions("booking:manage")`；Service 签名不变 → Router 无需改动 |
| `BookingStatus` 枚举 | [models.py:12-17](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L12-17)：`BOOKED=1 / CANCELLED=2 / CHECKED_IN=3 / COMPLETED=4 / NO_SHOW=5` |

## 并发场景示意（修复前 vs 修复后）

**修复前（无锁，TOCTOU 竞态）**

```
T1: BEGIN; SELECT status FROM bookings WHERE id=10;  -- BOOKED
T2: BEGIN; SELECT status FROM bookings WHERE id=10;  -- BOOKED（T1 未提交，T2 读到旧值）
T1: UPDATE bookings SET status=CHECKED_IN WHERE id=10; COMMIT;  -- 签到成功
T2: UPDATE bookings SET status=CHECKED_IN WHERE id=10; COMMIT;  -- 又签到成功（重复）
```

**修复后（FOR UPDATE 行锁序列化）**

```
T1: BEGIN; SELECT ... FROM bookings WHERE id=10 FOR UPDATE;  -- 拿到行锁，status=BOOKED
T2: BEGIN; SELECT ... FROM bookings WHERE id=10 FOR UPDATE;  -- 阻塞等锁
T1: status==BOOKED → UPDATE SET status=CHECKED_IN; COMMIT;  -- 释放锁
T2: 拿到锁，重新读 status=CHECKED_IN → 抛 BusinessException("当前预约状态无法签到") → ROLLBACK
```

## Scope（In Scope）

1. `booking/service.py`：
   - `check_in_booking`：`self.repo.get_by_id(db, booking_id)` → `self.repo.get_by_id_for_update(db, booking_id)`；status 检查逻辑不变（拿到锁后读取即为重检）。
   - `complete_booking`：同上替换。
   - 变量名语义清晰化（可选：`booking` → `locked_booking`，与 `_do_cancel_booking` 对齐），但不改返回逻辑。
2. 新增集成测试 `apps/api/tests/integration/test_checkin_complete_lock.py`：
   - 并发签到：`asyncio.gather` 模拟 2 个并发 `check_in`，断言一个 200、一个业务失败（"当前预约状态无法签到"）。
   - 并发完成：同上模式，断言一个 200、一个业务失败（"当前预约状态无法完成"）。
   - 正常单签到 / 单完成仍成功。
   - 状态校验：已 `CHECKED_IN` 再签到 → 失败；已 `COMPLETED` 再完成 → 失败。

## Out of Scope

- 不修改 `booking/repository.py`（`get_by_id_for_update` 已存在）。
- 不修改 `booking/router.py`（Service 签名不变，端点装饰器不变）。
- 不修改 OpenAPI 契约（路径/方法/请求体/响应模型不变）。
- 不修改前端 4 端（admin-web / student-web / teacher-web / miniapp）。
- 不修改 MCP（`check_in`/`complete` 不在 MCP Tool 集合内）。
- 不修改 DB 结构、不新增索引（FOR UPDATE 按主键命中，已有 `bookings.id` 主键索引）。
- 不引入 `skip_locked`（与 `get_by_id_for_update` 既有约定一致：写操作排队序列化而非快速失败；cancel 已用此模式）。
- 不为 check_in/complete 增加归属校验（F2.2 已说明归属校验属另一 Feature 范围；当前 check_in/complete 仅 `booking:manage` 权限角色可调）。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1：两个并发 `POST /bookings/{id}/check-in` 只有一个成功（200），另一个业务失败（400，msg 含"无法签到"）。
- AC-2：两个并发 `POST /bookings/{id}/complete` 只有一个成功（200），另一个业务失败（400，msg 含"无法完成"）。
- AC-3：正常单签到（BOOKED → CHECKED_IN）成功；`checked_in_at` 被设置。
- AC-4：正常单完成（BOOKED → COMPLETED 或 CHECKED_IN → COMPLETED）成功。
- AC-5：已 `CHECKED_IN` 再签到 → 400"当前预约状态无法签到"。
- AC-6：已 `COMPLETED` 再完成 → 400"当前预约状态无法完成"。
- AC-7：回归 `test_booking_ownership.py`、`test_auth_api.py` 全量通过。
- AC-8：分层合规——Service 走 Repository 的 `get_by_id_for_update`（不裸 SQL、不绕过 Repository）；事务边界在 Service（`db.commit()` 仍在 Service 内）。

## Dependencies

- 复用：`BookingRepository.get_by_id_for_update`（既有，含租户过滤）。
- 无新外部依赖；无 DB 结构变更；无 Redis key 变更；无 OpenAPI 变更；无前端影响。

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他调用方直接调 `BookingService.check_in_booking` / `complete_booking`（不经 router） | grep 已确认仅 router 两处调用；MCP 无 check_in/complete 工具。Service 签名不变，即便有遗漏调用方也不受影响 |
| U2 | 并发测试是否可能因 live_server 单进程串行处理请求而无法真正复现竞态 | live_server 是真实 Uvicorn 进程，FastAPI 在同一事件循环内 `await` 数据库 IO 时会切换协程，两个并发 HTTP 请求的 DB 读会交错 → 真实复现 TOCTOU；修复前必能复现双签到，修复后必能序列化。测试用 `asyncio.gather` 同时发起两请求 |
| U3 | `with_for_update()` 在测试库（PostgreSQL）是否生效 | 项目 DB 为 PostgreSQL（`DATABASE_URL` 指向 docker 共享开发库），`SELECT ... FOR UPDATE` 原生支持；`get_by_id_for_update` 已被 cancel_booking 使用并验证 |
