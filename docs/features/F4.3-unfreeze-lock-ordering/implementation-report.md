# F4.3 — 解冻批量操作锁排序 · 实施报告

> 日期：2026-09-29 ｜ 执行：backend-engineer（database-engineer 评审锁顺序/死锁语义）
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

按 [implementation-plan.md](./implementation-plan.md) 完成 F4.3 两个核心子任务 + 1 个扩展修复：
- **T4.3.1**：`unfreeze_and_cancel_conflicts` 在 `for conflict_id in conflict_card_ids:`（[service.py L907](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L907)）之前插入 `conflict_card_ids = sorted(conflict_card_ids)`（[service.py L906](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L906)）。
- **T4.3.2**：`unfreeze_and_freeze_conflicts` 同模式插入 `conflict_card_ids = sorted(conflict_card_ids)`（[service.py L1041](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1041)）。
- **扩展修复（D6 决策）**：`batch_cancel_cards` 同模式插入 `card_ids = sorted(card_ids)`（[service.py L1602](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1602)），消除同事务内多卡 `FOR UPDATE` 顺序加锁的死锁风险。

每处改动前均带 `# F4.3` 注释，引用 `.trae/rules/database/transaction.md §锁顺序`。`get_card_with_lock`（`SELECT ... FOR UPDATE`）、事务边界、状态机、容量校验、Service 方法签名均未改动。

## 2. 变更明细

### 2.1 `apps/api/src/app/modules/membership/service.py`（3 处各 3 行：注释 2 行 + sorted 1 行）

| 改动点 | 修复前 | 修复后 |
|--------|---------|---------|
| `unfreeze_and_cancel_conflicts` L904-907 | `for conflict_id in conflict_card_ids:`（无 sorted） | `# F4.3: ...` 注释 + `conflict_card_ids = sorted(conflict_card_ids)` + `for conflict_id in conflict_card_ids:` |
| `unfreeze_and_freeze_conflicts` L1039-1042 | 同上 | 同上 |
| `batch_cancel_cards` L1599-1603 | `for card_id in card_ids:`（无 sorted） | `# F4.3: ...` 注释 + `card_ids = sorted(card_ids)` + `for card_id in card_ids:` |

要点：
- `sorted(list[int])` 返回新列表（不 mutate 调用方入参），升序排列。
- 不去重（保持原语义，见 requirement U3）。
- 不改 `get_card_with_lock`（`with_for_update()` 锁机制不变）。
- 不改事务边界（仍由 Router `db.commit()` 统一提交）。
- 不改方法签名、不改返回结构、不改状态机。

### 2.2 `apps/api/tests/unit/test_unfreeze_lock_ordering.py`（新建）

- 用 monkeypatch spy 替换 `MembershipCardService.get_card_with_lock`（实例属性覆盖类方法，调用时不绑定 `self`），记录 `card_id` 调用顺序。
- FakeCard 用 `SimpleNamespace` 构造（主卡 `FROZEN` + `frozen_remaining_days=10`；conflict 卡 `ACTIVE` + `expire_at`）。
- mock db 用 `SimpleNamespace(add=MagicMock(), flush=AsyncMock(), ...)`；mock `freeze_repo.list_freezes` 返回 `([], 0)`。
- 8 用例覆盖 AC-1~AC-6：
  - `test_unfreeze_and_cancel_sorts_conflict_ids`（AC-1）
  - `test_unfreeze_and_freeze_sorts_conflict_ids`（AC-2）
  - `test_batch_cancel_sorts_card_ids`（AC-3，扩展修复）
  - `test_unfreeze_and_cancel_empty_list_safe` / `test_unfreeze_and_freeze_empty_list_safe`（AC-4）
  - `test_unfreeze_and_cancel_single_element_safe` / `test_unfreeze_and_freeze_single_element_safe`（AC-5）
  - `test_concurrent_callers_converge_to_global_order`（AC-6，spy 等价证明：两个反序请求经 sorted 后加锁顺序收敛到全局升序）

## 3. 实施中发现的问题

| # | 问题 | 处置 |
|---|------|------|
| 1 | `unfreeze_and_cancel_conflicts` 与 `unfreeze_and_freeze_conflicts` 的 `for conflict_id in conflict_card_ids:` 字符串相同，Edit old_string 不唯一 | 用包含前驱上下文（`cancelled_cards=[]/failed_cards=[]` vs `frozen_cards=[]/failed_cards=[]/now=...`）的更长 old_string 区分，确保精确匹配 |
| 2 | `batch_cancel_cards` 内 `card_ids` 是参数名而非 `conflict_card_ids`，Feature Task T4.3.1/T4.3.2 字面只覆盖 unfreeze 两方法 | 决策 D6：按用户提示实施方案第 2 条"一并修复同模式方法"指令，对 `batch_cancel_cards` 加 `card_ids = sorted(card_ids)`；改动同构、不扩大业务逻辑改动面；在文档透明记录 |
| 3 | `unfreeze_and_freeze_conflicts` 内 conflict 卡需 `expire_at` 字段计算 `frozen_remaining_days`（L1055-1059） | FakeConflict 构造时设 `expire_at=now+timedelta(days=30)`，覆盖该路径 |
| 4 | conftest session 级 autouse fixture 会启动 Redis 检查 + DB seed，对 unit 测试也会触发 | dev 环境 Redis/DB 可用（F4.2 已验证），unit 测试仍跑通；测试本身用 mock 不依赖真 DB，conftest autouse 仅环境前置 |
| 5 | 工作树存在其他 Feature 的未提交改动（repository.py/router.py/schemas.py/models.py/scheduler.py/ai/router.py/migration 等） | 本 Feature 未触碰这些文件；改动落点严格限定为 service.py 3 处 sorted + 新建测试 + 新建文档；在 static-verification §4 透明记录工作树状态 |

## 4. 与计划的偏差

- 计划列出的 2 个核心 Task（T4.3.1/T4.3.2）+ 1 个扩展修复（D6 决策的 `batch_cancel_cards`）全部按方案交付，无新增计划外源文件改动（除文档与测试）。
- 测试用例数 8（计划列 6 用例 + AC-6 并发等价证明 1 用例 + freeze 路径单元素 1 用例，最终拆为 8 个独立用例，覆盖更细），与计划方向一致无冲突。
- 测试放 `tests/unit/` 而非 `tests/integration/`（决策 D8：spy 测试用 mock 不依赖真 DB，unit 语义名副其实）。

## 5. 数据兼容与迁移

- **无 DB 结构变更**：不动 schema、不动 migration、不动 alembic_version。
- **无数据变更**：`sorted` 仅改变内存中 conflict_card_ids 的遍历顺序，不写库。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。
- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变 → 无需 `pnpm gen:types`，前端 4 端无影响。
- Service 方法签名（`unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` / `batch_cancel_cards`）不变。

## 6. 测试结果

- `test_unfreeze_lock_ordering.py`（单元）：**8 passed**（0.07s）
- 回归 `test_cancel_schedule_rollback.py`（F2.4）：**12 passed**（2.94s）
- 回归 `test_checkin_complete_lock.py` + `test_booking_ownership.py`（membership 卡加锁/所有权）：**19 passed**（5.99s）
- **合计 39 passed**，无失败。
- py_compile（service.py + test）：`COMPILE_OK_ALL`。
- app import 冒烟：单元测试 `from app.modules.membership.service import MembershipCardService` 成功（测试导入即冒烟）。

详见 [runtime-test-report.md](./runtime-test-report.md) 与 [static-verification.md](./static-verification.md)。
