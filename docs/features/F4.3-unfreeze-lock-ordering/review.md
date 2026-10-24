# F4.3 — Review

> 日期：2026-09-29 ｜ 审查人：backend-engineer（自审 + database-engineer 评审锁顺序/死锁语义 + 规则清单）

## Scope

- 变更严格限于 Feature 定义：
  1. `apps/api/src/app/modules/membership/service.py` 3 处各加 `# F4.3` 注释 + `sorted(...)`：
     - `unfreeze_and_cancel_conflicts` L904-906（T4.3.1）
     - `unfreeze_and_freeze_conflicts` L1039-1041（T4.3.2）
     - `batch_cancel_cards` L1599-1602（扩展修复，D6 决策）
  2. 新增测试 `apps/api/tests/unit/test_unfreeze_lock_ordering.py`（8 用例覆盖 AC-1~AC-6）。
- `get_card_with_lock` / Repository / Router / schemas / OpenAPI / migration / DB schema / 前端 / MCP **均未改动**。
- 未引入新依赖、未改 OpenAPI 路径/方法/请求体/响应模型、未改 Redis、未改 Service 方法签名。

## Architecture

- 分层合规：改动在 Service 层（`MembershipCardService`），非 Router / Repository；`sorted` 是 Python builtin，不涉及 SQL / DB schema。
- 事务边界：仍由 Router `db.commit()` 统一提交（[router.py:337/353/479](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L337)）；Service 不自行 commit；`sorted` 在循环前注入即可生效，未触碰 commit。
- 租户隔离：`get_card_with_lock` 内 `WHERE tenant_id = :val`（[service.py:494-495](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L494-495)）保证租户隔离；`sorted` 不影响 `tenant_id` 过滤语义。
- AI 边界：grep `ai/` 确认 `unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` / `batch_cancel_cards` 未被任何 MCP Tool 调用 → AI 层无影响。
- 锁顺序规则（[transaction.md §锁顺序](file:///Users/lixiang/Desktop/class_booking_system/.trae/rules/database/transaction.md#L24)）：多行加锁按固定顺序（升序）防死锁，符合规则。

## Code

- 3 处改动模式同构：注释 2 行（`# F4.3: ...` + 引用 transaction.md）+ `sorted(...)` 1 行。
- `sorted(list[int])` 返回新列表（不 mutate 调用方入参），升序；不去重（保持原语义，见 requirement U3）。
- 每处注释带 `F4.3` 标识便于追溯；引用 `.trae/rules/database/transaction.md §锁顺序` 便于审查。
- `unfreeze_and_cancel_conflicts` 与 `unfreeze_and_freeze_conflicts` 的 `for conflict_id in conflict_card_ids:` 字符串相同，用包含前驱上下文（`cancelled_cards=[]` vs `frozen_cards=[]`）的更长 old_string 精确匹配，未误改。

## Security

- 无端点变更；`@require_roles("admin", "super_admin")`（[router.py:305/467](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L305)）未动。
- 租户隔离：`get_card_with_lock` 的 `WHERE tenant_id=:val` 不变；`sorted` 不影响租户过滤。
- 认证：`get_current_user` 未动；`tenant_id` / `operator_id` 仍来自已认证上下文（[router.py:313-314/456-457/474-475](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L313)）。
- `conflict_card_ids` 仍来自请求体（`data.get`），但其内卡 ID 必须经 `get_card_with_lock` 的 `tenant_id` 校验——跨租户卡会被 `WHERE tenant_id=:val` 拒绝（404）→ 排序不引入新的跨租户风险。

## Transaction / Concurrency

- **核心修复**：消除"解冻批量操作 + 批量作废"三路径的并发死锁风险。
  - 修复前：`unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` 在单事务内对 `conflict_card_ids` 逐卡 `SELECT ... FOR UPDATE`，遍历顺序来自请求体（[router.py:317](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L317)），客户端可任意传入；两个并发请求反序传入时循环等待 → PG 死锁检测 abort 一方（`DeadlockFound`）。`batch_cancel_cards` 同模式（`cancel_card` 内 `get_card_with_lock`）。
  - 修复后：三方法均在循环前 `sorted(...)`，所有并发请求对同一组卡按全局升序加锁 → 循环等待条件被打破 → 死锁不可能。
- **锁持有期**：锁在循环内逐卡获取，持有至 Router `db.commit()`；`sorted` 确保整个循环内获取顺序一致。
- **失败隔离不变**：`unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` 的 `failed_cards` 隔离逻辑（单卡异常计入 failed_cards，不中断循环）不变；`batch_cancel_cards` 同。排序仅改变 failed_cards 内顺序，不影响隔离语义。
- **主卡加锁不变**：主卡 `card_id` 在循环外先加锁（L895/L1026），不参与 conflict 列表排序；两个并发请求处理同一主卡时第二方在主卡上排队，循环等待不成立（见 requirement U2）。
- **并发等价证明**：AC-6 用例 `test_concurrent_callers_converge_to_global_order` 证明两个反序请求经 sorted 后加锁顺序均收敛到 `[1,2,3]` → 全局总序 → 无死锁。

## Regression

- `test_cancel_schedule_rollback.py`（F2.4，12/12）：**12/12 通过** → AC-7 满足。
- `test_checkin_complete_lock.py` + `test_booking_ownership.py`（19/19）：membership 卡加锁/所有权路径不被破坏。
- 本 Feature 仅 Service 层加 3 处 `sorted`，不改 `get_card_with_lock` / 事务边界 / 状态机 / Repository / Router / schemas → 业务逻辑零回归风险。
- 关键：`sorted` 仅改变 conflict_card_ids 的遍历顺序，不改变单卡处理逻辑（状态流转、流水生成、容量校验不变）。

## Acceptance

- AC-1（cancel 排序）：`test_unfreeze_and_cancel_sorts_conflict_ids` 通过。
- AC-2（freeze 排序）：`test_unfreeze_and_freeze_sorts_conflict_ids` 通过。
- AC-3（batch 排序）：`test_batch_cancel_sorts_card_ids` 通过。
- AC-4（空列表）：`test_unfreeze_and_cancel_empty_list_safe` + `test_unfreeze_and_freeze_empty_list_safe` 通过。
- AC-5（单元素）：`test_unfreeze_and_cancel_single_element_safe` + `test_unfreeze_and_freeze_single_element_safe` 通过。
- AC-6（死锁预防）：`test_concurrent_callers_converge_to_global_order` 通过（spy 等价证明）。
- AC-7（回归）：F2.4 12/12 + checkin/ownership 19/19 通过。
- AC-8（分层合规）：静态 grep 验证仅 Service 改动；Repository / DB / Router / schemas / OpenAPI 零改动（详见 [static-verification.md](./static-verification.md)）。
- AC-9（契约不变）：无端点变更；Service 方法签名不变；无需 `pnpm gen:types`。

## 遗留事项（不阻塞）

1. **未做真实双连接反序死锁复现测试**：原因见 runtime-test-report §6（结果不稳定 + 基建成本高）；spy 等价证明已覆盖核心保证；生产灰度后建议观察 `pg_stat_activity` 的 lock 等待与 `DeadlockFound` 日志是否清零。
2. **`conflict_card_ids` 的 Pydantic 强校验未做**：当前 router 用 `data.get("conflict_card_ids", [])` 是 dict 弱取值；强校验（list[int] + 非空 + 去重）属契约增强，超出本 Feature Scope；如需可另立 Feature。
3. **`batch_cancel_cards` 扩展修复不在 Feature Task 列表内**：本 Feature 按"消除死锁风险"Goal + 用户提示实施方案"一并修复同模式方法"指令扩展修复；改动同构、风险极低；已在文档透明记录（D6 决策）。
4. **工作树存在其他 Feature 未提交改动**：本 Feature 未触碰；service.py 的 6 行（3 注释 + 3 sorted）是本 Feature 唯一引入点，与 grep 结果一致。

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 生产是否已发生过死锁 | 无生产日志可查；代码路径分析确证风险存在（同事务内多卡 FOR UPDATE 顺序加锁 + 入参顺序由前端控制）；本 Feature 为预防性修复 |
| U2 | 其他模块是否有同模式批量加锁 | grep `for .*card_ids` / `for conflict_id` / `get_card_with_lock` 全仓：除本 Feature 三方法外，`get_card_with_lock` 其余调用点（L624/726/768/822/1150/1250/1342/1420/1499/1538）均为单卡加锁（非循环批量），booking / schedule 模块未见同模式 → 范围完整 |
| U3 | 重复 ID 入参的 sorted 行为 | `sorted` 不去重，重复 ID 仍被循环处理（同事务行锁不自锁），与修复前语义一致（见 requirement U3） |

## 结论

**READY_FOR_ACCEPTANCE → CLOSE**
