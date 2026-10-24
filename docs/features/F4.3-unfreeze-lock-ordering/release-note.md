# F4.3 — Release Note

## 解冻批量操作锁排序（2026-09-29）

### 功能变更

- `MembershipCardService` 的三个批量加锁方法在循环前对卡 ID 列表排序后再加锁，消除并发死锁风险：
  - `unfreeze_and_cancel_conflicts`（[service.py:906](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L906)）：`conflict_card_ids = sorted(conflict_card_ids)`。
  - `unfreeze_and_freeze_conflicts`（[service.py:1041](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1041)）：同上。
  - `batch_cancel_cards`（[service.py:1602](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1602)）：`card_ids = sorted(card_ids)`（同模式扩展修复）。
- 三方法均对 `conflict_card_ids` / `card_ids` 在 `for ... in ...:` 循环前 `sorted(...)`，使所有并发请求对同一组卡按全局升序加锁（`SELECT ... FOR UPDATE`），打破 Coffman 死锁"循环等待"条件 → 死锁不可能。
- 遵守 [transaction.md §锁顺序](file:///Users/lixiang/Desktop/class_booking_system/.trae/rules/database/transaction.md#L24)：多表/多行加锁按固定顺序防死锁。

### 兼容性

- API 路径、方法、请求体、响应模型全部不变；无端点变更 → 无需 `pnpm gen:types`。
- Service 方法签名（`unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` / `batch_cancel_cards`）不变。
- 返回结构不变（`sorted` 仅改变 `failed_cards` / `cancelled_cards` / `frozen_cards` 列表内顺序，不影响结构）。
- 前端 4 端影响评估：
  - admin-web / teacher-web / student-web / miniapp：不直接感知 Service 内 `sorted`；端点契约不变 → **均不涉及**。
- `get_card_with_lock` / Repository / Router / schemas / OpenAPI / migration / DB schema / MCP **零改动**。

### 修复

- 消除并发死锁风险：
  - 修复前：两个并发请求对同一组冲突卡以相反顺序传入 `conflict_card_ids`（如 A:[3,1,2] / B:[1,2,3]）时，各自持有先入锁并等待对方持有的锁，触发 PostgreSQL 死锁检测器 abort 一方（`DeadlockFound`，500 错误，业务回滚）。
  - 修复后：所有并发请求对同一组卡按 `sorted(set)` 全局升序加锁，循环等待条件被打破，死锁不可能。
- 修复路径覆盖"解冻并作废冲突卡"、"解冻并冻结冲突卡"、"批量作废会员卡"三个批量加锁路径。

### 运维与数据

- **无数据库结构变更**：不动 schema、不动 migration、alembic_version 不变。
- **无数据变更**：`sorted` 仅改变内存中卡 ID 列表的遍历顺序，不写库。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。
- 生产灰度后建议观察 `pg_stat_activity` 的 `wait_event_type='lock'` 与日志中的 `DeadlockFound` 是否清零（修复前若有）。

### 部署步骤

```bash
# 1. 无 migration（本 Feature 不动 DB schema）

# 2. 验证（单元测试 + 回归）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_unfreeze_lock_ordering.py -v
# 期望：8 passed

cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_cancel_schedule_rollback.py tests/integration/test_checkin_complete_lock.py tests/integration/test_booking_ownership.py -v
# 期望：31 passed（12 + 19，回归不破）

# 3. py_compile 冒烟
cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile src/app/modules/membership/service.py && echo "COMPILE_OK"
# 期望：COMPILE_OK
```

### 已知遗留（后续处理）

- 真实双连接反序死锁复现测试未做：原因见 runtime-test-report §6（结果不稳定 + 基建成本高）；spy 等价证明已覆盖核心保证。
- `conflict_card_ids` 的 Pydantic 强校验（list[int] + 非空 + 去重）未做：属契约增强，超出本 Feature Scope；如需可另立 Feature。
- `batch_cancel_cards` 扩展修复不在 Feature Task 列表内：本 Feature 按"消除死锁风险"Goal + 用户提示"一并修复同模式方法"指令扩展修复；改动同构、风险极低。
