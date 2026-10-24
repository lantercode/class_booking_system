# F2.3 — 签到/完成加行锁 · 实施报告

> 日期：2026-09-28 ｜ 执行：backend-engineer
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

按 [implementation-plan.md](./implementation-plan.md) 完成签到/完成加行锁：`check_in_booking` / `complete_booking` 由无锁的 `get_by_id` 改为 `get_by_id_for_update`（SELECT ... FOR UPDATE，含租户过滤），与既有 `_do_cancel_booking` 同构。两个子任务 T2.3.1 / T2.3.2 全部交付。Service 签名不变，Router / Repository / OpenAPI / 前端 / MCP 均未改动。

## 2. 变更明细

### 2.1 `apps/api/src/app/modules/booking/service.py`（两处改动）

| 方法 | 改动 | 行号 |
|------|------|------|
| `check_in_booking` | `self.repo.get_by_id(db, booking_id)` → `self.repo.get_by_id_for_update(db, booking_id)`；变量 `booking` → `locked_booking`；补 docstring 与并发安全注释；status 检查逻辑不变（拿到锁后读取即为重检） | L275-303 |
| `complete_booking` | 同上模式 | L305-332 |

要点：
- 行锁序列化并发请求：第一个拿锁 → 写 → commit 释放；第二个拿锁后重新读 status → 业务异常拒绝（"当前预约状态无法签到/完成"）。
- 不引入 `skip_locked`：与 `get_by_id_for_update` 既有约定一致（写操作排队序列化，第二个请求应看到前一个的提交结果并据此拒绝）。
- 事务边界仍在 Service：`await db.commit()` / `await db.refresh(locked_booking)` 不变；锁随 AsyncSession 在 commit 后释放。
- `_to_response(locked_booking)` 同步更新调用方。

### 2.2 `apps/api/tests/integration/test_checkin_complete_lock.py`（新建）

- session-scoped `lock_data` fixture 搭建共享 course + schedule（engine 在 fixture 内 dispose，只返回纯数据，避免跨 loop）。
- function-scoped `local_db` fixture 为每用例提供独立 engine + session_factory（绑定当前用例事件循环）。
- 9 用例：AC-1~AC-6 + 补充场景（CHECKED_IN→COMPLETED、CANCELLED 签到失败、不存在 404）。
- 并发测试用 `asyncio.gather` 同时发起两请求，真实复现 PG 行锁竞争。

## 3. 实施中发现的问题

| # | 问题 | 处置 |
|---|------|------|
| 1 | 首轮测试 `RuntimeError: ... attached to a different loop`（asyncpg 跨事件循环） | 根因：`lock_data`（session-scoped）创建的 engine/session_factory 被各 function-scoped 用例跨 loop 复用。修复（借鉴 F2.2 `test_service_level_student_path_like_mcp` 模式）：`lock_data` 只返回纯数据 dict（engine 在 fixture 内 dispose）；新增 `local_db`（function-scoped）供 helpers。修复后 9/9 全绿 |

## 4. 与计划的偏差

- 计划列出的 2 个文件（service.py 改动 + 新测试）全部按方案交付，无新增计划外源文件改动。
- 实施中仅对测试文件做了 1 处工程性调整（事件循环隔离，见第 3 节），不涉及业务代码逻辑变更。

## 5. 数据兼容与迁移

- 无 DB 结构变更，无迁移。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。
- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变；Service 签名不变 → 无需 `pnpm gen:types`，前端 4 端无影响。
