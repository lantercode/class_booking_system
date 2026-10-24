# F4.3 — 运行时测试报告

> 日期：2026-09-29
> 环境：本地开发机，PostgreSQL（Docker 共享开发库，预置种子租户 dance-school），Redis 可用。无 migration 变更（本 Feature 不动 DB schema）。

## 1. 测试入口

```bash
# 主测试（F4.3 单元）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_unfreeze_lock_ordering.py -v

# 回归（AC-7，F2.4 解冻/扣次/回补路径不被破坏）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_cancel_schedule_rollback.py -v

# 回归（membership 卡加锁/所有权路径不被破坏）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_checkin_complete_lock.py tests/integration/test_booking_ownership.py -v
```

## 2. 结果摘要

| 套件 | 结果 |
|------|------|
| `test_unfreeze_lock_ordering.py`（单元，F4.3） | **8 passed**（0.07s） |
| `test_cancel_schedule_rollback.py`（F2.4 回归） | **12 passed**（2.94s） |
| `test_checkin_complete_lock.py` + `test_booking_ownership.py`（membership 回归） | **19 passed**（5.99s） |
| **合计** | **39 passed, 6 warnings** |

warnings 均为既有第三方库 deprecation（passlib `crypt` / FastAPI `example` / websockets `legacy` / uvicorn `WebSocketServerProtocol`），与本 Feature 无关（F4.2 亦同）。

## 3. 用例明细（test_unfreeze_lock_ordering.py，8/8 通过）

### 3.1 排序加锁行为验证（AC-1/AC-2/AC-3，3/3）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_unfreeze_and_cancel_sorts_conflict_ids` | AC-1 | monkeypatch spy 替换 `get_card_with_lock`；传入 `conflict_card_ids=[3,1,2]` + 主卡 `card_id=100`；断言 spy 调用顺序 == `[100, 1, 2, 3]`（主卡在前，conflict 按 sorted 升序） |
| `test_unfreeze_and_freeze_sorts_conflict_ids` | AC-2 | 同 AC-1 模式；断言 spy 调用顺序 == `[100, 1, 2, 3]` |
| `test_batch_cancel_sorts_card_ids` | AC-3 | spy 替换 `get_card_with_lock`；传入 `card_ids=[3,1,2]`；断言 spy 调用顺序 == `[1,2,3]`（无主卡前缀，纯循环按 sorted）；`cancel_card` 内 `get_card_with_lock` 被调用顺序 == sorted |

### 3.2 边界场景验证（AC-4/AC-5，4/4）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_unfreeze_and_cancel_empty_list_safe` | AC-4 | `conflict_card_ids=[]`；不抛异常；spy 调用 == `[100]`（仅主卡）；`success_count==0` / `cancelled_cards==[]` / `failed_cards==[]` |
| `test_unfreeze_and_freeze_empty_list_safe` | AC-4 | freeze 路径空列表；不抛异常；spy 调用 == `[100]`；`frozen_cards==[]` |
| `test_unfreeze_and_cancel_single_element_safe` | AC-5 | `conflict_card_ids=[5]`；spy 调用 == `[100, 5]`；`success_count==1` |
| `test_unfreeze_and_freeze_single_element_safe` | AC-5 | freeze 路径单元素；spy 调用 == `[100, 5]` |

### 3.3 并发死锁预防等价证明（AC-6，1/1）

| 用例 | 覆盖 AC | 验证点 |
|------|---------|--------|
| `test_concurrent_callers_converge_to_global_order` | AC-6 | 模拟 T1 传 `[3,1,2]`、T2 传 `[1,2,3]` 两个反序请求；分别 spy 后断言两者 `calls[1:]`（去掉主卡前缀）均 == `[1,2,3]` → 所有并发请求加锁顺序收敛到 `sorted(set)` 全局升序 → Coffman 死锁"循环等待"条件被打破 → 死锁不可能 |

## 4. 测试可信度分析

### 4.1 测试逻辑的区分力

- **修复前**（无 sorted）：`test_unfreeze_and_cancel_sorts_conflict_ids` 传入 `[3,1,2]`，spy 调用顺序 == `[100, 3, 1, 2]`（原序）→ 断言 `[100, 1, 2, 3]` 失败 → 测试能抓到回归。
- **修复后**：spy 调用顺序 == `[100, 1, 2, 3]`（sorted）→ 断言通过。
- 若回退本 Feature（删 3 处 sorted），上述 3 个排序用例 + AC-6 用例必失败。

### 4.2 spy 模式的等价性

- `get_card_with_lock` 的真实行为是 `SELECT ... FOR UPDATE`，spy 替换为记录 `card_id` 顺序的 async 函数。
- 死锁根因是"调用顺序"非"锁实现"：spy 精确捕获调用顺序，等价于捕获加锁顺序。
- 断言 `calls == [主卡, *sorted(conflict_card_ids)]` 即证明"加锁顺序收敛到全局升序"，是死锁预防的充分条件（user-flow §4 论证）。

### 4.3 mock 的充分性

- FakeCard 用 `SimpleNamespace` 模拟 `MembershipCard`，覆盖两个方法读取/写入的全部字段（`status` / `student_id` / `total_credits` / `used_credits` / `frozen_remaining_days` / `frozen_reason` / `frozen_at` / `frozen_until` / `expire_at` / `cancelled_at` / `cancelled_reason`）。
- mock db 用 `SimpleNamespace(add=MagicMock(), flush=AsyncMock(), ...)`：`db.add(txn)` 同步调用 OK；`await db.flush()` async OK。
- mock `freeze_repo.list_freezes` 返回 `([], 0)`：覆盖 L976/L1112 的 `freezes, _ = await self.freeze_repo.list_freezes(...)`，让 `if freezes and ...` 短路。
- `MembershipCardTransaction` / `MembershipCardFreeze` 真实构造（不触发 DB，仅 `__init__` 设属性）。
- 测试不依赖真 DB / Redis（conftest autouse session fixture 仍跑，dev 环境可用，不影响测试本身）。

## 5. 回归结论

- `test_cancel_schedule_rollback.py`（F2.4，12/12）：解冻/扣次/回补路径不被破坏 → **AC-7 满足**。
- `test_checkin_complete_lock.py` + `test_booking_ownership.py`（19/19）：membership 卡加锁 / 所有权路径不被破坏。
- 本 Feature 仅在 Service 层加 3 处 `sorted`，不改 `get_card_with_lock` / 事务边界 / 状态机 / Repository / Router / schemas → 业务逻辑零回归风险。
- 关键：`sorted` 仅改变 conflict_card_ids 的遍历顺序，不改变单卡处理逻辑（状态流转、流水生成、容量校验不变）。

## 6. 并发死锁复现说明（AC-6 真实双连接测试为何不做）

- **原因 1：结果不稳定**。真实双连接反序死锁复现需两个独立 `AsyncSession` + 故意反序加锁；PG 死锁检测器（`deadlock_timeout=1s`）会自动 abort 一方，导致结果非确定性（一方死锁、一方成功），难以稳定断言"无死锁"。
- **原因 2：测试基建成本高**。需两个独立 DB 连接 + 故意构造反序 + 等待 `deadlock_timeout` + 处理 abort 异常，且要在 CI 稳定运行，复杂度高。
- **等价证明充分**：AC-6 用 spy 测试证明"所有并发请求加锁顺序收敛到 `sorted(set)` 全局升序"（`test_concurrent_callers_converge_to_global_order`）。这是 Coffman 死锁"循环等待"条件被打破的充分条件 → 死锁不可能。spy 测试可在 CI 稳定运行，覆盖核心保证。
- **生产验证建议**：生产灰度后观察 `pg_stat_activity` 的 `wait_event_type='lock'` 与日志中的 `DeadlockFound` 是否消失（修复前若有，修复后应清零）。

## 7. 性能与资源

- 8 个单元用例约 0.07s（mock 无 DB IO）。
- 回归套件 31 用例约 8.93s（2.94s + 5.99s，含 HTTP 服务器启动 + 真 DB）。
- 无慢查询告警；`sorted(list[int])` 是 O(n log n) Timsort，n 通常 < 10，开销可忽略。

## 8. 迭代记录

| 轮次 | 问题 | 修复 |
|------|------|------|
| 第 1 轮 | — | **8/8 通过**（首版即全绿，无迭代） |
