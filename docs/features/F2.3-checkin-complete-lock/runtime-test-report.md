# F2.3 — 运行时测试报告

> 日期：2026-09-28
> 环境：本地开发机，FastAPI 测试服务器（127.0.0.1:8765，conftest 自动拉起的真实 Uvicorn 进程，独立线程 + 独立事件循环），PostgreSQL（Docker 共享开发库，预置种子租户 dance-school），Redis 可用。

## 1. 测试入口

```bash
# 主测试（F2.3）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_checkin_complete_lock.py -v

# 回归（AC-7）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest \
  tests/integration/test_booking_ownership.py \
  tests/integration/test_auth_api.py -v
```

## 2. 结果摘要

| 套件 | 结果 |
|------|------|
| `test_checkin_complete_lock.py` | **9 passed**（2.80s） |
| `test_booking_ownership.py`（回归） | **10 passed** |
| `test_auth_api.py`（回归） | **25 passed** |
| **合计** | **44 passed, 4 warnings** |

warnings 均为既有第三方库 deprecation（passlib `crypt`、uvicorn/websockets legacy、FastAPI `example`），与本 Feature 无关。

## 3. 用例明细（test_checkin_complete_lock.py，9/9 通过）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_single_check_in_ok` | AC-3 | BOOKED → CHECKED_IN；200；data.status=3；DB 终态=3；`checked_in_at` 非空 |
| `test_single_complete_ok` | AC-4 | BOOKED → COMPLETED；200；data.status=4；DB 终态=4 |
| `test_concurrent_check_in_only_one_succeeds` | AC-1 | `asyncio.gather` 同时发 2 个 check-in；codes==[200,400]；失败的 msg 含"无法签到"；无 Traceback；DB 终态=3 |
| `test_concurrent_complete_only_one_succeeds` | AC-2 | `asyncio.gather` 同时发 2 个 complete；codes==[200,400]；失败的 msg 含"无法完成"；DB 终态=4 |
| `test_check_in_already_checked_in_fails` | AC-5 | 已 CHECKED_IN 再签到 → 400"无法签到"；状态不变 |
| `test_complete_already_completed_fails` | AC-6 | 已 COMPLETED 再完成 → 400"无法完成"；状态不变 |
| `test_complete_from_checked_in_ok` | 补充 | CHECKED_IN → COMPLETED 成功（complete 接受 BOOKED\|CHECKED_IN） |
| `test_check_in_cancelled_fails` | 补充 | CANCELLED 预约签到 → 400"无法签到"（状态校验覆盖） |
| `test_check_in_nonexistent_returns_404` | 补充 | 不存在 booking 签到 → 404"不存在"（含租户过滤，不泄露存在性） |

## 4. 并发测试可信度分析

### 4.1 测试逻辑的区分力（修复前 vs 修复后）

- **修复前（无锁 TOCTOU）**：两并发请求同时读到 `BOOKED` → 都通过 status 检查 → 都写 `CHECKED_IN` → codes==[200,200] → `assert codes == [200, 400]` **失败**。
- **修复后（FOR UPDATE 序列化）**：第一个拿锁 → 写 → commit；第二个拿锁后读到 `CHECKED_IN` → 400 → codes==[200,400] → **通过**。

当前 9/9 通过 → 证明 FOR UPDATE 行锁已生效。若回退本 Feature 改动，`test_concurrent_check_in_only_one_succeeds` / `test_concurrent_complete_only_one_succeeds` 必失败（双签到/双完成）。

### 4.2 真实并发性保障

- `live_server` 是真实 Uvicorn 进程（独立线程 + 独立 asyncio loop），非 ASGITransport in-process。
- 两个 HTTP 请求经 `asyncio.gather` 同时发出（httpx AsyncClient 连接池并发）→ live_server 端 FastAPI 在第一个请求 `await repo.get_by_id_for_update`（DB IO）时切换协程处理第二个请求 → 两请求的 `SELECT ... FOR UPDATE` 在 PostgreSQL 层面真正争抢同一行锁。
- 第一个请求 commit 释放锁后，第二个请求拿到锁、重新读取 `status`（此时已是 `CHECKED_IN`/`COMPLETED`）→ 业务异常拒绝 → 400。
- 因此测试是真实并发场景的复现，非 mock。

### 4.3 事件循环隔离（迭代修复）

首轮测试出现 `RuntimeError: ... attached to a different loop`（asyncpg 跨事件循环复用 connection）。根因：`lock_data`（session-scoped）在 session loop 创建的 engine/session_factory 被各 function-scoped 用例跨 loop 复用。

**修复**（借鉴 F2.2 `test_service_level_student_path_like_mcp` 模式）：
- `lock_data` 改为只返回纯数据 dict（tenant_id / student_id / schedule_id），engine 在 fixture 内创建并 dispose，不向外暴露。
- 新增 `local_db`（function-scoped）fixture，为每个用例创建独立 engine + session_factory，绑定当前用例事件循环，供 helper 做 setup/assert/cleanup。
- HTTP 请求经 `client` fixture 到 live_server（独立 loop + 独立 engine）；PG 行锁在数据库层面跨连接生效，与测试进程的 helper 不互相干扰。

修复后 9/9 全绿，无跨 loop 错误。

## 5. 回归结论

- `test_booking_ownership.py`（10/10）+ `test_auth_api.py`（25/25）全部通过 → **AC-7 满足**。
- 预约归属（F2.2）、认证（JWT 双 token / 黑名单 / refresh）、RBAC 行为未受本 Feature 影响。
- 本 Feature 改动的 `check_in_booking` / `complete_booking` 仅把 `get_by_id` 换为 `get_by_id_for_update`，未改 Service 签名 / 端点契约 / 状态机分支条件 → 对调用方（router）透明，回归零风险。

## 6. 性能与资源

- 9 个加锁测试用例约 2.80s（含 fixture 一次性搭建课程+排期 + 每用例独立 booking 创建/清理）。
- FOR UPDATE 按主键 `bookings.id` 命中（已有主键索引），不锁表；不同 booking 间无锁竞争；正常单请求仅 SELECT 多 `FOR UPDATE` 子句，额外开销可忽略。
- 全部 44 用例（含回归）约 10.8s，无慢查询告警。

## 7. 迭代记录

| 轮次 | 问题 | 修复 |
|------|------|------|
| 第 1 轮 | `lock_data`（session-scoped）创建的 engine/session_factory 被各 function-scoped 用例跨 loop 复用 → asyncpg `attached to a different loop`，4 failed 5 passed | 重构：`lock_data` 只返回纯数据（engine 在 fixture 内 dispose）；新增 `local_db`（function-scoped）供 helpers 用 |
| 第 2 轮 | — | **9/9 通过**（首轮修复后即全绿） |
