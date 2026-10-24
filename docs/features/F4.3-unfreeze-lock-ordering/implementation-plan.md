# F4.3 — 解冻批量操作锁排序 · 实施方案

> Feature ID：F4.3
> 作者：backend-engineer（database-engineer 评审锁顺序/死锁语义）
> 日期：2026-09-29
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

`MembershipCardService` 的两个批量解冻方法在同一个 `AsyncSession` 内对 `conflict_card_ids` 列表逐卡调用 `get_card_with_lock`（`SELECT ... FOR UPDATE`），遍历顺序直接来自请求体（[router.py:317](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L317) `data.get("conflict_card_ids", [])`），无排序。两个并发请求对同一组卡以相反顺序传入时，各自持有先入锁并等待对方持有的锁，触发 PostgreSQL 死锁检测器 abort 一方（`DeadlockFound`）。

同模式问题存在于 `batch_cancel_cards`（[service.py:1592](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1592)）：循环 `card_ids` 调 `cancel_card`，`cancel_card` 内部 `get_card_with_lock`，单事务内多卡 `FOR UPDATE` 顺序加锁，同样可被反序并发请求死锁。

直接修复：在循环之前对 ID 列表 `sorted(...)`，使所有并发请求对同一组卡的加锁顺序收敛到全局升序，打破 Coffman 死锁"循环等待"条件。

## 已核查的代码与 DB 事实（Evidence）

| 事实 | 证据 |
|------|------|
| `unfreeze_and_cancel_conflicts` 循环无 sorted | [service.py:904](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L904)：`for conflict_id in conflict_card_ids:` |
| `unfreeze_and_freeze_conflicts` 循环无 sorted | [service.py:1036](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1036)：`for conflict_id in conflict_card_ids:` |
| `batch_cancel_cards` 循环无 sorted | [service.py:1592](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1592)：`for card_id in card_ids:` |
| `get_card_with_lock` 用 `SELECT ... FOR UPDATE` | [service.py:482-504](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L482-504)：`.with_for_update()` |
| `conflict_card_ids` 来自请求体（顺序无保证） | [router.py:317](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L317) `data.get("conflict_card_ids", [])` |
| `card_ids` 来自请求体 Pydantic | [router.py:469](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L469) `MembershipCardBatchCancelRequest` + L477 `data.card_ids` |
| 事务边界由 Router 控制 | [router.py:337/353/479](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L337)：Router `await db.commit()` 统一提交 |
| 锁顺序规则 | [transaction.md:24](file:///Users/lixiang/Desktop/class_booking_system/.trae/rules/database/transaction.md#L24)：多表加锁按固定顺序防死锁 |
| `CardStatus` 枚举值 | [models.py:49-56](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L49-56)：PENDING=0 / ACTIVE=1 / EXPIRED=2 / FROZEN=3 / CANCELLED=6 |
| 其他 `get_card_with_lock` 调用点均为单卡 | grep 全仓 `get_card_with_lock`：L624/726/768/822/1150/1250/1342/1420/1499/1538 均在非循环路径内单卡加锁，无死锁风险 |
| `unfreeze_and_cancel_conflicts` 未被 MCP Tool 调用 | grep `ai/` 无 `unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` / `batch_cancel_cards` 命中 → AI 边界无影响 |

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/modules/membership/service.py` | 3 处各加 1 行 `sorted(...)`：`unfreeze_and_cancel_conflicts`（T4.3.1）/ `unfreeze_and_freeze_conflicts`（T4.3.2）/ `batch_cancel_cards`（扩展） |
| 2 | `apps/api/tests/unit/test_unfreeze_lock_ordering.py` | 新建，6 用例覆盖 AC-1~AC-5 + batch 扩展 |

**不在改动范围**：`get_card_with_lock` 本身 / Repository / Router / schemas / OpenAPI / migration / DB schema / 前端 4 端 / MCP / Redis / 其他 Service 方法。

## Exact Fix

### 1. `unfreeze_and_cancel_conflicts`（[service.py L904 前](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L904)）

```python
# 修复前（L904）
        for conflict_id in conflict_card_ids:

# 修复后
        # T4.3.1: 对 conflict_card_ids 排序后再加锁，消除并发死锁风险（见 .trae/rules/database/transaction.md §锁顺序）
        conflict_card_ids = sorted(conflict_card_ids)
        for conflict_id in conflict_card_ids:
```

### 2. `unfreeze_and_freeze_conflicts`（[service.py L1036 前](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1036)）

```python
# 修复前（L1036）
        for conflict_id in conflict_card_ids:

# 修复后
        # T4.3.2: 对 conflict_card_ids 排序后再加锁，消除并发死锁风险（见 .trae/rules/database/transaction.md §锁顺序）
        conflict_card_ids = sorted(conflict_card_ids)
        for conflict_id in conflict_card_ids:
```

### 3. `batch_cancel_cards`（[service.py L1592 前](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1592)，扩展修复）

```python
# 修复前（L1592）
        for card_id in card_ids:

# 修复后
        # 同模式批量加锁排序，消除并发死锁风险（见 .trae/rules/database/transaction.md §锁顺序）
        card_ids = sorted(card_ids)
        for card_id in card_ids:
```

要点：
- `sorted(list[int])` 返回新列表（不 mutate 调用方入参），升序排列。
- 不去重（保持原语义，重复 ID 由 `get_card_with_lock` 同事务内行锁不自锁 + 业务层重复处理，见 requirement U3）。
- 不改加锁逻辑本身（`get_card_with_lock` / `with_for_update()` 不动）。
- 不改事务边界（仍由 Router `db.commit()` 统一提交）。
- 不改方法签名、不改返回结构、不改状态机。

## 关键决策记录（Decision）

| # | 决策 | 理由 |
|---|------|------|
| D1 | 用 `sorted()` 而非手动 sort 或 heapq | `sorted` 是 Python builtin O(n log n) Timsort；对 `list[int]` 返回稳定升序新列表；不改入参（值语义安全）；可读性最高；无新依赖 |
| D2 | 不去重 | 去重会改业务行为（重复 ID 当前会被重复处理计入 failed_cards 或 cancelled_cards，是入参质量问题非死锁问题）；保持原语义降低回归面；requirement U3 明确 |
| D3 | 不改 `get_card_with_lock` | 锁机制本身正确（`SELECT ... FOR UPDATE`）；死锁根因是调用顺序非锁实现；改动面最小化原则 |
| D4 | 不改事务边界 | Service 层不自行 commit 是 [layering.md](file:///Users/lixiang/Desktop/class_booking_system/.trae/rules/architecture/layering.md) 与 [transaction.md](file:///Users/lixiang/Desktop/class_booking_system/.trae/rules/database/transaction.md) 的硬约束；排序在循环前注入即可生效，无需触碰 commit |
| D5 | 主卡不参与 conflict 列表排序 | 主卡 `card_id` 是独立参数，在循环外先加锁（L895/L1026），与 conflict 卡不在同一排序域；两个并发请求处理同一主卡时第二方在主卡上排队，循环等待不成立（见 requirement U2）；conflict 卡之间排序即可打破循环等待 |
| D6 | 扩展修复 `batch_cancel_cards` | Feature backlog Scope 仅列两个 unfreeze 方法；但用户提示实施方案第 2 条明确"如果有其他类似的批量加锁遍历方法也缺排序，一并修复（先 grep 确认）"。经 grep 确认 `batch_cancel_cards` 同模式同风险（单事务内多卡 `FOR UPDATE` 顺序加锁），按指令扩展修复；改动同构（1 行 `sorted`），不扩大业务逻辑改动面 |
| D7 | 测试用 monkeypatch spy 而非真 DB 死锁复现 | 真 DB 死锁复现需两个独立 `AsyncSession` + 故意反序，PG 死锁检测会自动 abort 一方使结果不稳定（一方死锁一方成功），难以稳定断言"无死锁"；spy 测试证明"加锁顺序收敛到 sorted 全局升序"是死锁预防的充分条件（等价证明），且可在 CI 稳定运行 |
| D8 | 测试放 `tests/unit/` 而非 `tests/integration/` | spy 测试用 mock（SimpleNamespace + AsyncMock）不依赖真 DB / Redis，是纯单元测试语义；放 `tests/unit/` 名副其实；`tests/integration/` 测试需真 DB 与 HTTP 服务器（conftest session 级 autouse fixture），与 spy 测试语义不符 |
| D9 | 测试覆盖 batch_cancel_cards 扩展修复 | 虽 `batch_cancel_cards` 不在 Feature Task 列表内，但 D6 决策一并修复，测试一并覆盖以保证修复有效；AC-3 单列 |

## Dependency Analysis

- 复用：既有 `MembershipCardService`、`get_card_with_lock`、`CardStatus` 枚举。
- 复用：既有测试种子数据（`dance-school` 租户，`tests/conftest.py` session 级 fixture）——但本 Feature 测试用 mock 不依赖种子数据，conftest autouse 仍会跑（dev 环境 Redis/DB 可用，不影响）。
- 无新外部依赖；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响；无 DB schema 变更。
- 契约：无端点变化 → 无需 `pnpm gen:types`，前端 4 端无影响。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 排序改变 `failed_cards` / `cancelled_cards` / `frozen_cards` 列表内顺序 | 低 | 列表内顺序无契约保证；下游消费方（前端展示）对顺序无依赖；且排序后顺序更可预测 |
| 重复 ID 入参的 `sorted` 行为 | 低 | `sorted` 不去重，重复 ID 仍被循环处理（同事务行锁不自锁），与修复前语义一致 |
| 主卡与 conflict 卡同 ID（理论不可能但防御性） | 低 | 主卡 `card_id` 与 conflict 列表 ID 在业务上不应重叠（解冻的卡不应在作废列表内）；若重叠，`sorted` 不影响（主卡在循环外先加锁，循环内同 ID 第二次 `get_card_with_lock` 同事务行锁不自锁） |
| 既有 membership 测试对 conflict 列表顺序有断言 | 低 | grep `conflict_card_ids` 在测试目录无命中；既有测试针对单卡状态/余额/流水断言，不针对列表内顺序 |
| batch_cancel_cards 扩展改动回归 | 低 | 改动同构（1 行 `sorted`），不改变 `cancel_card` 单卡逻辑；`test_cancel_schedule_rollback.py` 覆盖解冻/扣次/回补路径，对 batch_cancel 是有效回归（虽然 batch_cancel 可能未被该测试直接覆盖） |
| AI / MCP 边界 | 低 | grep 确认 `unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` / `batch_cancel_cards` 未被任何 MCP Tool 调用 → AI 层无影响 |

## Implementation Steps

1. 改 `service.py` 三处加 `sorted(...)` → py_compile。
2. 写 `tests/unit/test_unfreeze_lock_ordering.py`（6 用例）→ 迭代至全绿。
3. 静态审查 diff（仅 service.py + 新测试）。
4. 回归 `test_cancel_schedule_rollback.py`（F2.4）。
5. grep 确认未触碰 `get_card_with_lock` / Repository / Router / schemas / migration / OpenAPI。

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1 | `test_unfreeze_and_cancel_sorts_conflict_ids` |
| AC-2 | `test_unfreeze_and_freeze_sorts_conflict_ids` |
| AC-3 | `test_batch_cancel_sorts_card_ids` |
| AC-4 | `test_unfreeze_and_cancel_empty_list_safe` + `test_unfreeze_and_freeze_empty_list_safe` |
| AC-5 | `test_unfreeze_and_cancel_single_element_safe`（单元素 + 主卡调用顺序断言） |
| AC-6 | 设计论证（user-flow §4）+ spy 等价证明（AC-1/AC-2/AC-3 蕴含） |
| AC-7 | 回归 `test_cancel_schedule_rollback.py` |
| AC-8 | 静态 grep：仅 Service 改动；Repository / DB / Router / schemas / OpenAPI 零改动 |
| AC-9 | 静态 grep：端点 / DTO / OpenAPI 路径无变更；Service 方法签名不变 |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他模块的批量加锁遍历方法缺排序 | grep `for .*card_ids` / `for conflict_id` / `get_card_with_lock` 全仓：除本 Feature 三方法外，`get_card_with_lock` 其余调用点均为单卡加锁（非循环批量），booking / schedule 模块未见同模式批量 FOR UPDATE 遍历 → 范围完整 |
| U2 | `sorted` 是否对 `list[int]` 之外的入参类型安全 | `conflict_card_ids` 由 Pydantic 在 Router 层校验为 `list[int]`（实际 router 用 `data.get(...)` 是 dict 未强校验，但 Service 签名 `list[int]`）；`sorted(list[int])` 返回 `list[int]`；若入参非 list（异常情况）`sorted` 会抛 TypeError——与修复前 `for ... in ...` 抛 TypeError 行为一致，不引入新失败模式 |
| U3 | 生产环境是否已发生过死锁 | 无生产日志可查（dev 环境）；但代码路径分析确证风险存在（同事务内多卡 FOR UPDATE 顺序加锁 + 入参顺序由前端控制）；本 Feature 为预防性修复 |
| U4 | 是否需要补 `conflict_card_ids` 的 Pydantic 强校验（list[int] + 非空 + 去重） | 本 Feature 范围限定为锁排序；Pydantic 强校验属契约增强，超出 Scope；如需可另立 Feature（与本 Feature 解耦） |
