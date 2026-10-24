# F4.3 — 解冻批量操作锁排序 · 需求文档

> Feature ID：F4.3
> 作者：backend-engineer（协作 database-engineer 评审锁顺序与死锁语义）
> 日期：2026-09-29
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（后端 Service 层 + 数据库并发语义，双领域，backend 主笔、database 评审锁顺序；不动 DB schema / migration / Router / OpenAPI / 前端 / MCP）
> 依赖：无新外部依赖；复用既有 `MembershipCardService` 与 `get_card_with_lock`（`SELECT ... FOR UPDATE`）
> 前置 Feature：无（独立 bug-fix 类 Feature）

---

## Goal

消除"解冻并作废冲突卡 / 解冻并冻结冲突卡"两个批量加锁路径的死锁风险。两个方法在同一个 `AsyncSession` 内对 `conflict_card_ids` 列表逐卡调用 `get_card_with_lock`（`SELECT ... FOR UPDATE`），但当前遍历顺序直接来自请求体 `data.get("conflict_card_ids", [])`（[router.py:317](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L317)），客户端可任意传入顺序。若两个并发请求对同一组卡以相反顺序传入（A: [1,2,3] / B: [3,2,1]），各自持有先入锁并等待对方持有的锁，会触发 PostgreSQL 死锁检测（一方被 abort 抛 `DeadlockFound`）。

修复目标：在两个方法遍历 `conflict_card_ids` 之前对其排序（`sorted(conflict_card_ids)`），使所有并发请求对同一组卡按相同全局顺序加锁，消除循环等待条件（Coffman 死锁四条件之一："循环等待"被打破）。同时修复同模式的 `batch_cancel_cards`（同样在单事务内对多卡依次 `FOR UPDATE` 加锁，[service.py:1572-1609](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1572-1609)）。

## User Story

作为系统，
我希望"解冻并作废冲突卡"、"解冻并冻结冲突卡"、"批量作废会员卡"三个批量加锁路径对所有卡 ID 按固定全局顺序加锁，以便：
- 两个并发请求对同一组卡以任意顺序传入时，加锁顺序一致，不触发死锁。
- 遵守 [transaction.md §锁顺序](file:///Users/lixiang/Desktop/class_booking_system/.trae/rules/database/transaction.md#L24)（多表加锁按固定顺序防死锁）在"单表多行"维度的延伸约束。

作为运维，
我希望修复是单行 `sorted(...)` 注入，不改加锁逻辑本身、不改事务边界、不改状态机、不改容量校验，以便：
- 改动面最小、回归风险最低。
- 不引入新依赖、不改 DB schema、不改 migration、不改 Service 其他方法签名。
- 不破坏既有 `unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` / `batch_cancel_cards` 的对外契约与返回结构。

## Background / 现状（已核查的代码事实）

| 事实 | 证据 |
|------|------|
| `unfreeze_and_cancel_conflicts` 遍历 conflict_card_ids 未排序 | [service.py:904](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L904)：`for conflict_id in conflict_card_ids:` → L906 `conflict_card = await self.get_card_with_lock(db, conflict_id, tenant_id)` |
| `unfreeze_and_freeze_conflicts` 同模式未排序 | [service.py:1036](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1036)：`for conflict_id in conflict_card_ids:` → L1038 `conflict_card = await self.get_card_with_lock(db, conflict_id, tenant_id)` |
| `batch_cancel_cards` 同模式未排序 | [service.py:1592](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1592)：`for card_id in card_ids:` → L1595 `await self.cancel_card(...)` → [cancel_card L1538](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1538) `card = await self.get_card_with_lock(db, card_id, tenant_id)` |
| `conflict_card_ids` 来自请求体，顺序无保证 | [router.py:317](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L317)：`conflict_card_ids = data.get("conflict_card_ids", [])`（`data: dict = Body(...)`）；[router.py:469](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L469) `data: MembershipCardBatchCancelRequest = Body(...)` 的 `card_ids` 同样来自请求体 |
| `get_card_with_lock` 用 `SELECT ... FOR UPDATE` 悲观锁 | [service.py:482-504](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L482-504)：`.with_for_update()` 标准行级悲观锁 |
| 锁顺序规则要求固定顺序加锁 | [transaction.md:24](file:///Users/lixiang/Desktop/class_booking_system/.trae/rules/database/transaction.md#L24)：多表加锁按固定顺序，不得反向加锁，防死锁 |
| 同事务内多卡依次加锁 | 两个 unfreeze 方法共享传入的 `db: AsyncSession`，循环内 `get_card_with_lock` 拿锁后立即写卡状态、`db.add(txn)`，由 Router 层 `await db.commit()` 统一提交（[router.py:337/353](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L337)）→ 锁持有至 commit，覆盖整个循环 |
| `cancel_card` 同事务内对单卡加锁 | [cancel_card L1538](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1538) `get_card_with_lock`，L1569 `await db.flush()`；`batch_cancel_cards` 共享 db，由 [router.py:479](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L479) 统一 commit |

## 死锁机理（Why）

PostgreSQL 行级锁 `FOR UPDATE` 死锁四条件（Coffman）：
1. 互斥：`FOR UPDATE` 锁互斥。
2. 占有并等待：事务持锁 A 后再请求锁 B。
3. 不可剥夺：行锁释放只在事务结束。
4. 循环等待：T1 等 T2 持有的锁，T2 等 T1 持有的锁。

当前实现：T1 处理 [1,2,3]（锁 1 → 等 2），T2 处理 [3,2,1]（锁 3 → 等 2），双方各自持锁并等待对方持有的行 → 循环等待成立 → PG 死锁检测器（默认 `deadlock_timeout=1s`）abort 一方，抛 `sqlalchemy.exc.OperationalError` 包装的 `DeadlockFound`。

修复后：T1 与 T2 都按 `sorted([3,1,2])=[1,2,3]` 顺序加锁 → 先到者锁 1 → 后到者在 1 上排队（不持任何锁）→ 先到者继续锁 2、锁 3 → 提交释放 → 后到者获 1 → 锁 2 → 锁 3 → 提交。循环等待条件被打破，无死锁。

## Scope（In Scope）

1. `apps/api/src/app/modules/membership/service.py`：
   - `unfreeze_and_cancel_conflicts`（L871）：在 `for conflict_id in conflict_card_ids:`（L904）之前插入 `conflict_card_ids = sorted(conflict_card_ids)`（T4.3.1）。
   - `unfreeze_and_freeze_conflicts`（L1000）：在 `for conflict_id in conflict_card_ids:`（L1036）之前插入 `conflict_card_ids = sorted(conflict_card_ids)`（T4.3.2）。
   - `batch_cancel_cards`（L1572）：在 `for card_id in card_ids:`（L1592）之前插入 `card_ids = sorted(card_ids)`（扩展修复，同模式同风险）。
2. 新增单元测试 `apps/api/tests/unit/test_unfreeze_lock_ordering.py`：用 monkeypatch spy 替换 `MembershipCardService.get_card_with_lock`，记录调用顺序，验证排序行为；覆盖空列表 / 单元素 / 多元素无序 / batch 扩展。

## Out of Scope

- 不改 `get_card_with_lock` 本身（`with_for_update()` 锁机制不变）。
- 不改事务边界（仍由 Router 层 `db.commit()` 统一提交）。
- 不改状态机 / 容量校验 / 卡状态流转 / 流水生成逻辑（只加排序，不改业务规则）。
- 不改 Service 的其他方法签名（`unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` / `batch_cancel_cards` 签名不变）。
- 不改 Router / schemas / OpenAPI / 前端 4 端 / MCP。
- 不改 DB schema、不改 migration、不引入新依赖、不改 Redis key。
- 不处理其他模块的批量加锁（如 booking / schedule 模块未发现同模式批量 FOR UPDATE 遍历，见 UNKNOWN U1）。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1：`unfreeze_and_cancel_conflicts` 接收无序 `conflict_card_ids` 时，`get_card_with_lock` 的调用顺序 == `sorted(conflict_card_ids)`（主卡调用在前）。
- AC-2：`unfreeze_and_freeze_conflicts` 同上。
- AC-3：`batch_cancel_cards` 接收无序 `card_ids` 时，`get_card_with_lock` 的调用顺序 == `sorted(card_ids)`。
- AC-4：空列表 `conflict_card_ids=[]` 不报错（主卡仍解冻，无 conflict 加锁调用）。
- AC-5：单元素列表 `[5]` 不报错，`get_card_with_lock` 调用顺序 == `[card_id, 5]`。
- AC-6：并发死锁预防（设计论证 + spy 等价证明；真实双连接反序死锁复现不在测试基建内，见 runtime-test-report §6）。
- AC-7：回归不破现有行为（既有 membership / cancel-schedule-rollback 测试全绿）。
- AC-8：分层合规（Service 层改动；不改 Repository / DB / Router / OpenAPI）。
- AC-9：契约不变（无端点变更，无 DTO 变更，无需 `pnpm gen:types`）。

## Dependencies

- 复用：既有 `MembershipCardService`、`get_card_with_lock`（`SELECT ... FOR UPDATE`）。
- 复用：既有 `CardStatus` 枚举（`FROZEN=3` / `ACTIVE=1` / `PENDING=0` / `CANCELLED=6`，[models.py:49-56](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L49-56)）。
- 复用：既有测试种子数据（`dance-school` 租户，由 `tests/conftest.py` session 级 fixture 初始化）。
- 无新外部依赖；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响；无 DB schema 变更。
- 无前置 Feature 依赖。

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他模块的批量加锁遍历方法缺排序 | grep `for .*card_ids` / `for conflict_id` / `get_card_with_lock` 全仓：除本 Feature 三个方法外，`get_card_with_lock` 其余调用点（L624/726/768/822/1150/1250/1342/1420/1499/1538）均为单卡加锁（非循环批量），不存在死锁风险；booking / schedule 模块未见同模式批量 FOR UPDATE 遍历 → 本 Feature 范围完整 |
| U2 | 主卡（`card_id`）与 conflict 卡是否需要参与统一排序 | 不需要：主卡加锁（L895/L1026/L1499 等）在循环外、先于 conflict 卡循环加锁，且主卡 ID 是单独参数不在 conflict 列表内；两个并发请求若处理不同主卡则锁不同行无冲突，若处理同一主卡则第一方先锁主卡，第二方在主卡上排队，循环等待不成立。conflict 卡之间排序即可打破循环等待 |
| U3 | `sorted()` 对 `list[int]` 的稳定性与去重 | `sorted` 返回新列表不改原入参（参数语义为值传递，list 是可变引用但 `sorted` 返回新对象，不 mutate 调用方列表）；不去重（若 conflict_card_ids 含重复 ID，第二次 `get_card_with_lock` 同一行已在事务内持锁，PG 不会自锁，但业务层会重复处理同一卡——这是入参质量问题，不在本 Feature 范围；保持原不去重语义避免改业务行为） |
| U4 | 排序后失败列表 `failed_cards` 顺序是否变化 | `failed_cards` / `cancelled_cards` / `frozen_cards` 顺序会按排序后的 conflict_card_ids 顺序填充；这是更可预测的行为，且这些列表是结果返回（非加锁顺序），不影响死锁预防；下游消费方（前端展示）对列表内顺序无契约保证 → 安全 |
| U5 | `batch_cancel_cards` 是否在 Feature 定义范围内 | Feature backlog Scope 仅列两个 unfreeze 方法；用户提示实施方案第 2 条明确"如果有其他类似的批量加锁遍历方法也缺排序，一并修复（先 grep 确认）"。`batch_cancel_cards` 经 grep 确认同模式同风险（单事务内多卡 `FOR UPDATE`），按指令扩展修复并在文档透明记录（见 implementation-plan.md 决策 D6） |
