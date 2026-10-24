# F4.3 — 解冻批量操作锁排序 · 验收标准

> 每条 AC 均可通过单元测试（`tests/unit/test_unfreeze_lock_ordering.py`）或回归测试验证。
> 测试入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_unfreeze_lock_ordering.py -v`
> 回归入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_cancel_schedule_rollback.py -v`

| # | AC | 验证方式 | 预期 |
|---|----|---------|------|
| AC-1 | `unfreeze_and_cancel_conflicts` 接收无序 conflict_card_ids 时按 sorted 顺序加锁 | UT：monkeypatch spy 替换 `MembershipCardService.get_card_with_lock`，记录 card_id 调用顺序；传入 `conflict_card_ids=[3,1,2]` + 主卡 `card_id=0` | spy 调用顺序 == `[0, 1, 2, 3]`（主卡在前，conflict 卡按 sorted 升序） |
| AC-2 | `unfreeze_and_freeze_conflicts` 同上 | UT：同 AC-1 模式 | spy 调用顺序 == `[0, 1, 2, 3]` |
| AC-3 | `batch_cancel_cards` 接收无序 card_ids 时按 sorted 顺序加锁（扩展修复） | UT：monkeypatch spy；传入 `card_ids=[3,1,2]` | spy 调用顺序 == `[1, 2, 3]`（无主卡参数，纯循环） |
| AC-4 | 空列表不报错 | UT：`conflict_card_ids=[]` + 主卡 mock | 不抛异常；`get_card_with_lock` 仅被调用 1 次（主卡）；返回 `success_count == 0` |
| AC-5 | 单元素列表不报错 | UT：`conflict_card_ids=[5]` + 主卡 `card_id=0` | 不抛异常；spy 调用顺序 == `[0, 5]`；`success_count == 1` |
| AC-6 | 并发死锁预防 | 设计论证（user-flow §4 Coffman 循环等待条件被打破）+ spy 等价证明（AC-1/AC-2/AC-3：所有并发请求加锁顺序收敛到 `sorted(set)` 全局升序） | 真实双连接反序死锁复现不在测试基建内（PG 死锁检测自动 abort 一方使结果不稳定，难以稳定断言"无死锁"），见 runtime-test-report §6 |
| AC-7 | 回归不破现有行为 | 回归：`test_cancel_schedule_rollback.py` + 既有 membership 相关测试 | 全部通过 |
| AC-8 | 分层合规 | 静态：仅 Service 层改动；不改 Repository / DB / migration / Router / schemas / OpenAPI / 前端 / MCP | 无违规 |
| AC-9 | 契约不变 | 静态：grep 端点 / DTO / OpenAPI 路径无变更；Service 方法签名不变 | 无需 `pnpm gen:types`，前端 4 端无影响 |

## 辅助断言

- AC-1a：主卡 `get_card_with_lock` 调用先于所有 conflict 卡调用（顺序索引 0）。
- AC-1b：conflict 卡之间的调用顺序严格升序（`calls[1:] == sorted(conflict_card_ids)`）。
- AC-3a：`batch_cancel_cards` 内 conflict 卡（`card_ids`）调用顺序严格升序，无主卡前缀（`calls == sorted(card_ids)`）。
- AC-4a：空列表时 `sorted([])` 返回 `[]`，循环不执行，方法返回结构含 `success_count=0` / `failed_cards=[]` / `cancelled_cards=[]`（或 `frozen_cards=[]`）。
- AC-7a：回归测试 `test_cancel_schedule_rollback.py` 全绿（F2.4 Feature 既有用例覆盖解冻/扣次/回补路径，对排序改动是有效回归）。

## HTTP 状态码与信封约定（对照 contracts.md）

- 本 Feature 无 HTTP 端点变更，无新增信封/状态码。
- `failed_cards` 非空时仍返回 400 + `{code: 400, msg, data: {message, failed_cards}}`（既有行为不变，排序仅改变 `failed_cards` 内卡 ID 顺序，不影响信封结构）。
- 死锁（修复前可能）由 PG 抛 `DeadlockFound` 经全局异常处理器返回 500 信封；修复后此路径不再触发，无需新增异常处理。

## 不在 AC 范围（明确排除）

- 不验证"重复 ID 入参"的去重行为（保持原不去重语义，见 requirement U3）。
- 不验证"冲突卡跨租户"的拒绝行为（既有 `get_card_with_lock` 的 `WHERE tenant_id=:val` 已保证，非本 Feature 修复点）。
- 不验证状态机校验（既有 `card.status != FROZEN` 等校验不变，非本 Feature 修复点）。
