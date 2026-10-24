# F2.4 — 运行时测试报告

> 日期：2026-09-28
> 环境：本地开发机，FastAPI 测试服务器（127.0.0.1:8765，conftest 自动拉起的真实 Uvicorn 进程，独立线程 + 独立事件循环），PostgreSQL（Docker 共享开发库，预置种子租户 dance-school），Redis 可用。

## 1. 测试入口

```bash
# 主测试（F2.4）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_cancel_schedule_rollback.py -v

# 回归（AC-8）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest \
  tests/integration/test_checkin_complete_lock.py \
  tests/integration/test_booking_ownership.py \
  tests/integration/test_auth_api.py -v
```

## 2. 结果摘要

| 套件 | 结果 |
|------|------|
| `test_cancel_schedule_rollback.py` | **12 passed**（3.25s） |
| `test_checkin_complete_lock.py`（回归） | **9 passed** |
| `test_booking_ownership.py`（回归） | **10 passed** |
| `test_auth_api.py`（回归） | **25 passed** |
| **合计** | **56 passed, 4 warnings** |

warnings 均为既有第三方库 deprecation（passlib `crypt`、uvicorn/websockets legacy、FastAPI `example`），与本 Feature 无关。

## 3. 用例明细（test_cancel_schedule_rollback.py，12/12 通过）

### 3.1 Service 直调路径（TestCancelScheduleRollbackService，7/7）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_cancel_schedule_normal_ok` | AC-1 | 1 schedule(booked_count=1) + 1 BOOKED booking + 1 card(used_credits=1)；Service 直调 → 返回 `{total_bookings:1, success_count:1, failed_count:0, failed_bookings:[]}`；DB 终态 schedule=CANCELLED、booked_count=0、booking=CANCELLED、`cancelled_at` 非空、card.used_credits=0（恢复 1→0） |
| `test_cancel_schedule_restore_credit_failure_rolls_back_all` | AC-2 | `monkeypatch.setattr(MembershipCardService, "restore_credit", _fail_restore)` 抛 RuntimeError；`cancel_schedule` raise `BusinessException(code=500)`，msg 含"会员卡恢复次数失败"与"取消排期操作已撤销"；mock 调用计数==1；DB 终态 schedule=NORMAL、booked_count=1、booking=BOOKED、`cancelled_at`=None、card.used_credits=1（未恢复） |
| `test_cancel_schedule_partial_failure_rolls_back_prior_success` | AC-3 | 2 个不同 student 的 BOOKED booking + 2 card；mock 第 2 次调用 restore_credit 抛异常；`cancel_schedule` raise `BusinessException(500)`；mock 调用计数==2；DB 终态 schedule=NORMAL、booked_count=2、两 booking 都仍 BOOKED、两 `cancelled_at` 都仍 None、两 card.used_credits 都仍 1（第一个的恢复也回滚） |
| `test_cancel_schedule_no_bookings_ok` | AC-4 | 1 schedule(booked_count=0, 无 booking)；Service 直调 → 返回 `{total_bookings:0, success_count:0, ...}`；DB 终态 schedule=CANCELLED |
| `test_cancel_schedule_already_cancelled_fails` | AC-5 | 1 schedule(status=CANCELLED)；Service 直调 → raise `BusinessException(code=400)`，msg 含"已取消" |
| `test_cancel_schedule_finished_fails` | 补充 | 1 schedule(status=FINISHED)；Service 直调 → raise `BusinessException(code=400)`，msg 含"已完成" |
| `test_cancel_schedule_nonexistent_returns_404` | 补充 | schedule_id=999999999；Service 直调 → raise `NotFoundException`（404"排期不存在"） |

### 3.2 HTTP 端点路径（TestCancelScheduleRollbackHTTP，5/5）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_http_cancel_schedule_normal_ok` | AC-6 | super_admin token；HTTP `POST /schedules/{id}/cancel` → 200；body.code=0；data 字段 {schedule_id, total_bookings:1, success_count:1, failed_count:0}；msg 非空且不含 Traceback；DB 终态 schedule=CANCELLED、booking=CANCELLED、card.used_credits=0 |
| `test_http_cancel_schedule_restore_failure_rolls_back` | AC-7 | 构造 used_credits=0 的卡触发 `restore_credit` 真实抛 `HTTPException(400)` → 内层 except 包装为 `BusinessException(500)`；HTTP → 500；body.code=500；msg 含"会员卡恢复次数失败"与"取消排期操作已撤销"；msg 不含 Traceback / RuntimeError / HTTPException；DB 终态 schedule=NORMAL、booked_count=1、booking=BOOKED、`cancelled_at`=None、card.used_credits=0（原本就是 0，未变） |
| `test_http_cancel_schedule_already_cancelled_fails` | 补充 | HTTP 已 CANCELLED 排期再取消 → 400；body.code=400；msg 含"已取消" |
| `test_http_cancel_schedule_nonexistent_returns_404` | 补充 | HTTP 不存在 schedule → 404；body.code=404；msg 含"不存在" |
| `test_http_cancel_schedule_unauthorized_fails` | 补充 | 学员 token（无 `schedule:cancel` 权限）取消排期 → 403 |

## 4. 事务回滚可信度分析

### 4.1 测试逻辑的区分力（修复前 vs 修复后）

- **修复前（外层吞异常，脏提交）**：restore_credit 失败 → 外层 except 接住 → `failed_bookings.append(...)` → 循环继续 → `db.commit()` 提交部分变更 → DB 终态 schedule=CANCELLED、booking.status=CANCELLED、booked_count 已减、card.used_credits 未恢复。`test_cancel_schedule_restore_credit_failure_rolls_back_all` 断言 schedule.status==NORMAL、booking.status==BOOKED → **失败**。
- **修复后（异常传播，整体回滚）**：restore_credit 失败 → 内层 except 包装为 `BusinessException(500)` → raise 传播出方法 → `db.commit()` 永不执行 → AsyncSession ROLLBACK → DB 终态 schedule=NORMAL、booking=BOOKED、card.used_credits 未变。`test_cancel_schedule_restore_credit_failure_rolls_back_all` 断言通过 → **证明事务回滚已生效**。

当前 12/12 通过 → 证明修复已生效。若回退本 Feature 改动（恢复外层 try/except），`test_cancel_schedule_restore_credit_failure_rolls_back_all` / `test_cancel_schedule_partial_failure_rolls_back_prior_success` / `test_http_cancel_schedule_restore_failure_rolls_back` 必失败（脏提交后 DB 终态非初始）。

### 4.2 真实事务性保障

- **Service 直调路径**：`async with local_db() as session:` 持有 AsyncSession；`cancel_schedule` 内部所有变更都在该 session；异常抛出后未 commit → `with` 退出时 AsyncSession 自动 rollback（SQLAlchemy 默认行为 `expire_on_commit=False` 不影响 rollback）；新 session 读 DB 验证终态（避免读到 dirty session）。
- **HTTP 端点路径**：FastAPI `get_session` 依赖在请求结束 finally 关闭 session；`cancel_schedule` raise → 未 commit → session 被 finally rollback；测试用 `local_db` 独立 session 读 DB 验证终态。

### 4.3 mock 与真实失败的双路径设计

- **Service 直调路径用 monkeypatch**：精确控制 `restore_credit` 抛异常的时机（第 1 次 / 第 2 次）；验证 mock 调用计数；但仅作用于测试进程，对 live_server 不生效。
- **HTTP 端点路径用真实失败场景**：构造 `used_credits=0` 的卡触发 `restore_credit` 内部 `if card.used_credits <= 0: raise HTTPException(400)` → 被内层 except 包装为 `BusinessException(500)`；既端到端验证全链路（含全局异常处理器、信封、不泄露），又精确触发回滚路径。

两条路径互补：Service 直调路径精确控制 mock + 直接读 DB 断言；HTTP 端点路径验证全链路契约 + 信封 + 不泄露。

### 4.4 事件循环隔离（借鉴 F2.2/F2.3）

- `rollback_data`（session-scoped）在 session loop 内创建并 dispose engine，只返回纯数据 dict（含临时 student IDs），不向外暴露 engine/session_factory。
- `local_db`（function-scoped）为每个用例创建独立 engine + session_factory，绑定当前用例事件循环。
- HTTP 请求经 `client` fixture 到 live_server（独立 loop + 独立 engine）；PG 行锁与事务在数据库层面跨连接生效。

修复后 12/12 全绿，无跨 loop 错误。

## 5. 回归结论

- `test_checkin_complete_lock.py`（9/9）+ `test_booking_ownership.py`（10/10）+ `test_auth_api.py`（25/25）全部通过 → **AC-8 满足**。
- 签到/完成行锁（F2.3）、预约归属（F2.2）、JWT 双 token / 黑名单 / refresh、RBAC 行为未受本 Feature 影响。
- 本 Feature 改动的 `cancel_schedule` 仅重构事务模型（异常传播触发回滚），未改 Service 签名 / 端点契约 / 状态机分支条件 → 对调用方（router）透明，回归零风险。

## 6. 性能与资源

- 12 个测试用例约 3.25s（含 fixture 一次性搭建共享 course + 临时 student + 每用例独立 schedule/booking/card 创建/清理）。
- `decrement_booked_count` 的 `with_for_update` 按主键 `course_schedules.id` 命中（已有主键索引），不锁表；不同 schedule 间无锁竞争；正常单请求仅 SELECT 多 `FOR UPDATE` 子句，额外开销可忽略。
- `restore_credit` 内部 `get_card_with_lock` 的 `with_for_update` 按主键 `membership_cards.id` 命中（已有主键索引）。
- 全部 56 用例（含回归）约 14s（3.25s + 10.76s），无慢查询告警。

## 7. 迭代记录

| 轮次 | 问题 | 修复 |
|------|------|------|
| 第 1 轮 | 3 failed + 1 error：清理 card 时被 `MembershipCardTransaction` 外键引用阻塞 → session abort → schedule 也未清理 → 残留数据级联导致后续用例的 `uq_bookings_schedule_student_active` 唯一约束冲突 | (1) `_cleanup` 增加按 card_id 清理 txn 步骤；每步独立 session + commit；(2) `rollback_data` fixture 通过 admin HTTP 创建 2 个临时 student（student_a / student_b）供多 booking 场景使用，规避唯一约束 |
| 第 2 轮 | — | **12/12 通过**（首轮修复后即全绿） |
