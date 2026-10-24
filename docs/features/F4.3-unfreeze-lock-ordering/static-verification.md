# F4.3 — 静态验证报告

> 日期：2026-09-29

## 1. py_compile

```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
  src/app/modules/membership/service.py \
  tests/unit/test_unfreeze_lock_ordering.py && echo "COMPILE_OK_ALL"
```

实际执行：

```
$ cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
    src/app/modules/membership/service.py \
    tests/unit/test_unfreeze_lock_ordering.py && echo "COMPILE_OK_ALL"
COMPILE_OK_ALL
```

> IDE 报 "无法解析导入 fastapi/sqlalchemy/app.*" 为 linter 未识别 venv 的误报，py_compile 在 venv 下通过。

## 2. sorted 注入点核查

```bash
grep -n "F4.3\|sorted(conflict_card_ids)\|sorted(card_ids)" \
  apps/api/src/app/modules/membership/service.py
```

| 行 | 代码 | 所属方法 | 结论 |
|----|------|---------|------|
| L904-906 | `# F4.3: 对 conflict_card_ids 排序后再加锁...` + `conflict_card_ids = sorted(conflict_card_ids)` | `unfreeze_and_cancel_conflicts` | T4.3.1 已注入 |
| L1039-1041 | `# F4.3: 对 conflict_card_ids 排序后再加锁...` + `conflict_card_ids = sorted(conflict_card_ids)` | `unfreeze_and_freeze_conflicts` | T4.3.2 已注入 |
| L1599-1602 | `# F4.3: 对 card_ids 排序后再加锁...` + `card_ids = sorted(card_ids)` | `batch_cancel_cards` | 扩展修复（D6）已注入 |

**结论**：3 处 sorted 注入点全部到位，每处带 `# F4.3` 注释引用 transaction.md §锁顺序。

## 3. 分层合规检查

| 规则 | 检查 | 结果 |
|------|------|------|
| Service 层承载业务规则 | `sorted` 注入在 Service 层（`MembershipCardService`），非 Router / Repository | 通过 |
| 不改 Repository | `apps/api/src/app/modules/membership/repository.py` 未由本 Feature 修改（见 §4 工作树说明） | 通过 |
| 不改 Router / schemas | `router.py` / `schemas.py` 未由本 Feature 修改 | 通过 |
| 不改 DB schema / migration | 无新增 / 修改 alembic migration；alembic_version 不变 | 通过 |
| 事务边界归 Service 控制 | 仍由 Router `db.commit()` 统一提交；Service 不自行 commit；`sorted` 在循环前注入即可生效，未触碰 commit | 通过 |
| 不裸 SQL 直写业务数据 | `sorted` 是 Python builtin，不涉及 SQL；`get_card_with_lock` 的 `with_for_update()` 未动 | 通过 |
| 租户隔离 | `get_card_with_lock` 内 `WHERE tenant_id = :val`（[service.py:494-495](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L494-495)）保证租户隔离；`sorted` 不影响租户过滤语义 | 通过 |
| RBAC | 端点不变；`@require_roles("admin", "super_admin")`（[router.py:305/467](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L305)）未动 | 通过 |
| 认证 | `get_current_user` 未动；`tenant_id` / `operator_id` 仍来自已认证上下文 | 通过 |
| AI 边界 | grep `ai/` 无 `unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` / `batch_cancel_cards` 命中 → 不涉及 MCP（无 Tool 变更） | 通过 |
| 锁顺序规则（transaction.md §锁顺序） | 多行加锁按固定顺序（升序）防死锁，符合规则 | 通过 |

## 4. 改动落点核查

```bash
# 本 Feature 实际触碰（grep + 新建文件确认）
git status --short -- apps/api/tests/unit/ docs/features/F4.3-unfreeze-lock-ordering/ docs/delivery/feature-backlog.md
# ?? apps/api/tests/unit/test_unfreeze_lock_ordering.py
# ?? docs/features/F4.3-unfreeze-lock-ordering/
# ?? docs/delivery/feature-backlog.md
```

本 Feature 实际触碰：

| 文件 | 本 Feature 实际变化 | 审查结论 |
|------|------|---------|
| `apps/api/src/app/modules/membership/service.py` | 3 处各加 `# F4.3` 注释 + `sorted(...)`（L904-906 / L1039-1041 / L1599-1602） | T4.3.1 + T4.3.2 + 扩展修复，未动 `get_card_with_lock` / 事务 / 状态机 |
| `apps/api/tests/unit/test_unfreeze_lock_ordering.py` | 新建 | 8 用例覆盖 AC-1~AC-6 |
| `docs/features/F4.3-unfreeze-lock-ordering/` | 新建 9 产物 | SKILL.md 9 产物齐备 |
| `docs/delivery/feature-backlog.md` | 更新 F4.3 条目为 DONE | 对齐 F4.2 格式 |

**工作树状态说明（透明记录）**：工作树存在其他 Feature 的未提交改动（`repository.py` / `router.py` / `schemas.py` / `models.py` / `scheduler.py` / `ai/router.py` / 部分 migration 等显示 `M` 或 `??`），这些不属于 F4.3 范围，是用户进行中的其他工作；本 Feature 未触碰这些文件。本 Feature 的 service.py 改动严格限定为上述 3 处 sorted（共 6 行注释 + 3 行 sorted = 9 行），与 grep 结果一致。

## 5. `get_card_with_lock` 未改动核查

```bash
grep -n "with_for_update\|async def get_card_with_lock" \
  apps/api/src/app/modules/membership/service.py
```

| 行 | 代码 | 结论 |
|----|------|------|
| L482 | `async def get_card_with_lock(` | 方法签名未动 |
| L497 | `.with_for_update()` | 锁机制未动 |

**结论**：`get_card_with_lock` 的 `SELECT ... FOR UPDATE` 悲观锁机制零改动；本 Feature 只调调用顺序，不改锁实现。

## 6. 契约一致性

- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变（无端点变更）。
- Service 方法签名（`unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` / `batch_cancel_cards`）不变。
- 返回结构不变（`sorted` 仅改变 `failed_cards` / `cancelled_cards` / `frozen_cards` 列表内顺序，不影响结构）。
- 前端 4 端影响评估：
  - admin-web / teacher-web / student-web / miniapp：不直接感知 Service 内 `sorted`；端点契约不变 → **均不涉及**。
- 无需 `pnpm gen:types`。

## 7. 异常处理一致性

- `failed_cards` 非空时仍由 Service 抛 `HTTPException(400, detail={message, failed_cards})`，经全局异常处理器返回统一信封（既有行为不变）。
- 排序后 `failed_cards` 内卡 ID 顺序按 sorted 升序，更可预测，不影响信封结构。
- 死锁（修复前可能）由 PG 抛 `DeadlockFound` 经全局异常处理器返回 500 信封；修复后此路径不再触发，无需新增异常处理。
- Service 抛出的业务异常（`HTTPException`）仍按既有路径传播，不引入新异常类型。
