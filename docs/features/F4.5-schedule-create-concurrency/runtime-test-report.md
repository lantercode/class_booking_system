# F4.5 — 运行时测试报告

> 日期：2026-10-02（评审回修后重跑）
> 环境：本地开发机，PostgreSQL（Docker 共享开发库，预置种子租户 `dance-school` + 种子教师 13800138001），Redis 可用；alembic head=`f44ab1c2d3e4`（本 Feature 无 migration）。
> 运行方式：真实 asyncpg + 真实 PostgreSQL（非 SQLite / 非 mock DB）；并发用双独立 `AsyncSession` + `asyncio.gather`。

## 1. 测试入口

```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest -v \
  tests/integration/test_schedule_create_concurrency.py \
  tests/integration/test_status_check_constraints.py \
  tests/integration/test_booking_fk_membership_card.py \
  tests/integration/test_order_fk_membership_card.py \
  tests/integration/test_delete_schedule_service.py \
  tests/integration/test_cancel_schedule_rollback.py \
  tests/test_scheduler_tenant_isolation.py
```

## 2. 结果摘要（评审回修后一次合并运行）

| 套件 | 用例 | 结果 |
|------|------|------|
| `test_schedule_create_concurrency.py`（F4.5，含第 9 例评审回归） | 9 | **9 passed**（0.50s） |
| `test_status_check_constraints.py`（F4.4 回归） | 18 | passed |
| `test_booking_fk_membership_card.py`（F4.1 回归） | 6 | passed |
| `test_order_fk_membership_card.py`（F4.2 回归） | 7 | passed |
| `test_delete_schedule_service.py`（同模块） | 9 | passed |
| `test_cancel_schedule_rollback.py`（同模块） | 12 | passed |
| `test_scheduler_tenant_isolation.py`（同模块） | 9 | passed |
| **总计** | **70** | **70 passed, 0 fail**（5.86s） |

warnings 均为既有第三方 deprecation（passlib `crypt` / FastAPI `example` / unittest mock 未 await），与本 Feature 无关。

## 3. F4.5 用例明细（9/9）

| 类 / 用例 | 覆盖 AC | 验证点 | 结果 |
|-----------|---------|--------|------|
| `TestConcurrentCreateConflict::test_concurrent_overlapping_only_one_succeeds` | AC-1 | 双独立 session 同教师完全重叠（10:00~11:00）并发创建 | 成功=1；失败=1 且为 `BusinessException.code==400`；窗口 `COUNT==1` |
| `TestConcurrentCreateConflict::test_concurrent_partial_overlap_only_one_succeeds` | AC-1 | 30 分钟部分重叠（A 整点、B 半点起 1h） | 成功=1；失败=1 `BusinessException` |
| `TestConcurrentCreateNonOverlapping::test_concurrent_non_overlapping_both_succeed` | AC-2 | 同教师 10:00 与 12:00 两段不重叠 | 失败=0、成功=2；两 `id` 不同；两窗口各 1 行 |
| `TestSerializationFailureHandling::test_serialization_failure_retried_and_succeeds` | AC-3 | monkeypatch 首次 `find_conflicts` 抛真实 `asyncpg.SerializationError` | 返回 `id` 非空；`attempts==2`；窗口 1 行 |
| `TestSerializationFailureHandling::test_serialization_failure_exhausted_returns_business_error` | AC-4 | 持续注入 40001 | `BusinessException` 且 msg 含"重试"；`attempts==3`；窗口 0 行 |
| `TestSerialBehaviorUnchanged::test_serial_conflict_still_rejected` | AC-5 | 串行两次完全重叠 | 第二次 `BusinessException(400)`、msg 含"教师时间冲突"、窗口 1 行 |
| `TestSerialBehaviorUnchanged::test_serial_valid_create_succeeds` | AC-5 | 单个合法创建 | `id`/`teacher_id` 正确，`status==NORMAL`，`booked_count==0` |
| `TestSerialBehaviorUnchanged::test_invalid_time_range_rejected` | AC-5 | `end_at == start_at` | 事务外即抛 `ValidationException` |
| `TestLockedConflictRowNotSkipped::test_existing_conflict_row_locked_by_rc_tx_is_still_detected` | **AC-5b** | S 已提交；另一 RC 会话 `FOR UPDATE` 持 S 不提交；持锁窗口内探测 + 走 Service 同窗口创建 | `use_lock=True` 探测→空集（漏判根因）；`use_lock=False` 探测→见 S；Service 抛 `BusinessException(400)`「教师时间冲突」；窗口始终 1 行 |

## 4. AC-6 隔离级别 / SSI 实证结果（一次性诊断脚本，已清理，结论留痕）

### 4.1 真实进入 SERIALIZABLE（SHOW）

在 `rollback()` + `db.connection(execution_options={"isolation_level":"SERIALIZABLE"})` 之后：

| 路径 | `SHOW transaction_isolation` | PG notice |
|------|------------------------------|-----------|
| 全新 session（无上游事务） | `serializable` | `[]` |
| 先执行一条只读 SELECT（模拟认证 / RBAC 上游事务） | `serializable` | `[]` |
| 上述路径模拟一次失败后**重试**（再次 rollback + 提升） | `serializable` | `[]` |

对照组（修正前的裸 `text("BEGIN ISOLATION LEVEL SERIALIZABLE")`）：SHOW 亦为 `serializable`，但每次产生 `there is already a transaction in progress` 告警，且适配器内部重建事务对象——故改为官方写法。

### 4.2 保护来源因果对照（`asyncio.Barrier(2)`：两事务都完成冲突快照读后再插入）

| 隔离级别 + 锁写法 | worker 结果 | 落库行数 |
|-------------------|-------------|----------|
| SERIALIZABLE + 纯 SELECT | `40001_ABORT` / `COMMITTED` | **1** |
| SERIALIZABLE + `FOR UPDATE` | `COMMITTED` / `40001_ABORT` | **1** |
| SERIALIZABLE + `FOR UPDATE SKIP LOCKED`（旧调用用法，该场景） | `COMMITTED` / `40001_ABORT` | **1** |
| READ COMMITTED + 纯 SELECT（对照） | `COMMITTED` / `COMMITTED` | **2（漏洞）** |

结论（适用边界）：在"双方都从空谓词结果集出发"的前提下，三种 SELECT 写法在 SERIALIZABLE 下均由 SSI 谓词锁阻止空集双插；READ COMMITTED 下同一逻辑双写——隔离级别提升是必要条件。但该实验**不覆盖"已存在冲突行被第三方持锁"**：该场景见 §4.4，也是最终调用改为 `use_lock=False` 的依据。

### 4.3 诊断过程中的一次假阴性（已修正并记录）

首次对照脚本把连接池对象当作连接传入 worker（`pool.execute(...)` 每次取连接/归还，事务无法跨语句保持，伴随 `Resetting connection with an active transaction` 日志），导致 SER 组也双写。修正为"每个 worker `async with pool.acquire() as conn` 固定连接 + Barrier 同步"后结论即 4.2 表所示。该问题仅存在于一次性诊断脚本，不涉及产品代码与集成测试（集成测试本就使用独立持久 `AsyncSession`）。

### 4.4 持锁已存在冲突行（AC-5b，评审 NEEDS_FIX 的因果验证）

- 实验体即回归用例 `TestLockedConflictRowNotSkipped`（真实会话，非一次性脚本）：S 已提交 → RC 会话对 S `SELECT … FOR UPDATE` 持锁不提交。
- 持锁窗口内同一查询两种实参对比：`use_lock=True`（FOR UPDATE SKIP LOCKED）返回**空集**（S 被跳过）；`use_lock=False`（快照读）返回 **S**。
- Service 路径因果翻转：
  - 临时把调用点改回 `use_lock=True` 单跑该用例 → **FAILED: DID NOT RAISE BusinessException**（重叠行静默落库，漏判稳定复现，且无 40001）；
  - 还原 `use_lock=False` → **PASSED**：创建被 `BusinessException(400)` 拒绝、窗口始终 1 行。

## 5. 测试可信度分析

- **区分力**：AC-1 若回退为 READ COMMITTED，两事务读空集后双插 → 成功数=2、窗口行数=2，断言必失败；仅在 SERIALIZABLE + SSI 下才稳定出现"1 成功 + 1 业务异常 + 1 行"。
- **真实事务**：每个并发请求在各自 `async with sf() as session` 内完成"提升隔离→检查→插入→提交"，与生产请求线程模型一致（不同物理连接）。
- **终态独立核验**：成功后用独立 session 调 `_count_window` 统计落库行数，避免 dirty read。
- **注入真实异常**：AC-3/4 抛 `asyncpg.exceptions.SerializationError("could not serialize access ...")`，与生产 SSI 中止同族，验证 `_is_serialization_failure` 识别与重试/耗尽分支。
- **AC-5b 缺陷检出力经因果翻转验证**：同一用例在旧调用（`use_lock=True`）下实测 `DID NOT RAISE`、修复后 PASS，证明它不是"恒真断言"；用例内还同时固化了 `use_lock=True → 空集` 的漏判根因，防止未来误改回去。
- **数据隔离**：`capacity=78` + 2099 时间窗，避免与存量排期相互影响；每用例 finally 清理。

## 6. 回归结论（AC-8）

- F4.4（18/18）、F4.1（6/6）、F4.2（7/7）：全部通过。本 Feature 不改 bookings/orders/三表 status Check，也不改 migration/模型。
- 同模块 `test_delete_schedule_service.py`（9/9）、`test_cancel_schedule_rollback.py`（12/12）：仅改 `create_schedule`，删除/取消路径不受影响。
- `test_scheduler_tenant_isolation.py`（9/9）：APScheduler 租户循环逻辑不受影响。
- OpenAPI/前端契约零变更，无前端运行项。

## 7. 性能与资源

- F4.5 的 9 个并发用例 0.50s；含全部回归 70 用例一次合并运行 5.86s（主要为 HTTP/uvicorn 类用例启停）。
- SERIALIZABLE 仅作用于单个创建事务；冲突检查由行锁锁写改为快照谓词读，不再被他人行锁阻塞，走既有教师/教室时间索引。管理端排课为低频写，实测无慢查询。
- 生产高并发下的 40001 重试率无法在 dev 压测（见 requirement.md U1），建议监控；即便耗尽也仅友好失败，不产生重叠脏数据。

## 8. 迭代记录

| 轮次 | 问题 | 修复 / 结果 |
|------|------|-------------|
| 接手时 | 遗留代码 8/8 已绿，但裸 BEGIN 存疑、无产物 | 实证 SHOW/SSI/因果三组诊断 |
| 修正轮 | 裸 BEGIN 每请求 PG WARNING、依赖边界行为 | 改官方 `connection(execution_options=...)`，py_compile OK |
| 验证轮 | 修正后重跑 F4.5 8 用例 | 8 passed |
| 回归轮 | F4.1/F4.2/F4.4 + delete/cancel/scheduler | 60+9 全绿 |
| **评审轮** | 双专家评审：backend READY / **database NEEDS_FIX**（SKIP LOCKED 吞被 RC 持锁的已存在冲突行，SSI 不兜底） | 主控复现采纳：`use_lock=False` + docstring + 第 9 用例；旧代码因果对照 `DID NOT RAISE` |
| **回修验证轮** | 修复后全量重跑 | **F4.5 9/9 + 回归 61 = 70 passed, 0 fail（5.86s）** |
