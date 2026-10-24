# F4.3 — 解冻批量操作锁排序 · 用户流程

> 视角：本 Feature 为 Service 层并发语义修复，无 HTTP 端点变更、无 DB schema 变更。以下描述各调用路径在修复前后的加锁行为对比，供验收与回归参考。
> 业务身份链路（`current_user` / `tenant_id`）由 Router `get_current_user` 注入，不在本 Feature 范围；排序在 Service 层对身份链路透明。

---

## 流程 1：解冻并作废冲突卡（unfreeze_and_cancel_conflicts，正常路径）

调用链：`POST /api/v1/membership/cards/{card_id}/admin-unfreeze`（action=unfreeze_and_cancel）→ Router（[router.py:329-342](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L329-342)）→ `MembershipCardService.unfreeze_and_cancel_conflicts`（[service.py:871-998](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L871-998)）→ `db.commit()`（Router 统一提交）。

修复后加锁顺序：

1. 主卡加锁：`get_card_with_lock(db, card_id, tenant_id)` → `SELECT ... FOR UPDATE` 锁定主卡行。
2. 校验主卡状态 = `FROZEN`（否则 400）。
3. **新增**：`conflict_card_ids = sorted(conflict_card_ids)`（T4.3.1）。
4. 循环 `for conflict_id in conflict_card_ids:`（已排序）：
   - `get_card_with_lock(db, conflict_id, tenant_id)` 逐卡加锁。
   - 校验同租户同学生、状态 ∈ {ACTIVE, PENDING}。
   - 写卡状态 `CANCELLED`、流水 `EXPIRE` 清零、`db.add(txn)`。
5. 若 `failed_cards` 非空 → 抛 400（事务回滚，所有锁释放）。
6. 主卡状态 `FROZEN → ACTIVE`，按 `frozen_remaining_days` 重算 `expire_at`。
7. 记录主卡 `ADJUST` 流水、`db.add(txn)`。
8. `await db.flush()` → Router `await db.commit()` 提交并释放所有行锁。

**修复前**：步骤 4 按 `data.get("conflict_card_ids", [])` 原始顺序加锁；两个并发请求反序传入时触发死锁。
**修复后**：步骤 4 按全局升序加锁，并发请求加锁顺序一致，无死锁。

## 流程 2：解冻并冻结冲突卡（unfreeze_and_freeze_conflicts，正常路径）

调用链：`POST /api/v1/membership/cards/{card_id}/admin-unfreeze`（action=unfreeze_and_freeze）→ Router（[router.py:344-358](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L344-358)）→ `MembershipCardService.unfreeze_and_freeze_conflicts`（[service.py:1000-1134](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1000-1134)）→ `db.commit()`。

修复后加锁顺序：

1. 主卡加锁 + 校验 `FROZEN`。
2. **新增**：`conflict_card_ids = sorted(conflict_card_ids)`（T4.3.2）。
3. 循环（已排序）：`get_card_with_lock` 逐卡加锁 → 校验同学生、状态 = `ACTIVE` → 计算 `frozen_remaining_days`、`frozen_until`、`expire_at` 延期 → 写 `FROZEN` 状态、`db.add(MembershipCardFreeze)`。
4. 若 `failed_cards` 非空 → 400。
5. 主卡 `FROZEN → ACTIVE`、重算 `expire_at`、关闭最近一笔未关闭的 freeze 记录（`unfrozen_at = now`）。
6. 主卡 `ADJUST` 流水、`db.add(txn)`、`db.flush()` → Router `db.commit()`。

## 流程 3：批量作废会员卡（batch_cancel_cards，扩展修复）

调用链：`POST /api/v1/membership/cards/batch-cancel` → Router（[router.py:466-480](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L466-480)）→ `MembershipCardService.batch_cancel_cards`（[service.py:1572-1609](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1572-1609)）→ 内部循环调 `cancel_card`（[service.py:1523-1570](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1523-1570)）→ `db.commit()`。

修复后加锁顺序：

1. **新增**：`card_ids = sorted(card_ids)`（扩展修复）。
2. 循环 `for card_id in card_ids:`（已排序）：
   - `cancel_card(db, card_id, ...)` → 内部 `get_card_with_lock(db, card_id, tenant_id)` 加锁。
   - 校验非 `CANCELLED`、写 `CANCELLED` 状态、`EXPIRE` 流水清零、`db.flush()`。
3. 失败隔离：单卡抛 `HTTPException` / `Exception` 计入 `failed_cards`，不中断循环（但仍走完所有卡加锁）。
4. Router `db.commit()` 统一提交。

## 流程 4：并发场景对比（死锁预防，AC-6）

**场景**：两个管理员同时解冻同一组冲突卡 [3,1,2]，A 以 [3,1,2] 传入，B 以 [1,2,3] 传入（或任意反序组合）。

**修复前**：
```
T1 (action=A, ids=[3,1,2]): 锁3 → 等1（被T2持有）→ ... → 等2（被T2持有）
T2 (action=B, ids=[1,2,3]): 锁1 → 锁2 → 等3（被T1持有）
→ 循环等待 T1{3}⇄T2{1,2} → PG deadlock detector abort 一方（deadlock_timeout=1s）
→ 抛 DeadlockFound → 500 错误，业务回滚，前端需重试
```

**修复后**：
```
T1 (action=A, ids=[3,1,2]): sorted=[1,2,3] → 锁1 → 锁2 → 锁3 → commit
T2 (action=B, ids=[1,2,3]): sorted=[1,2,3] → 等1（T1持有）→ T1 commit 后获1 → 锁2 → 锁3 → commit
→ 无循环等待 → 无死锁
```

**等价证明**：所有并发请求对同一卡集合的加锁顺序都收敛到 `sorted(set)`，即按卡 ID 升序的全局总序。在全局总序下，每个事务要么"先获锁继续"要么"在前序卡上排队（不持任何锁）"，不存在"持有 A 等 B"与"持有 B 等 A"的对峙 → 循环等待条件不成立 → 死锁不可能。

**测试等价证明**（见 runtime-test-report §6）：用 monkeypatch spy 记录 `get_card_with_lock` 调用顺序，断言 == `sorted(...)`；这等价于证明"所有请求的加锁顺序收敛到全局升序"，即死锁预防的充分条件。真实双连接反序死锁复现需要两个独立 `AsyncSession` + 故意反序，但 PG 死锁检测会自动 abort 一方使结果不稳定（一方死锁、一方成功），难以稳定断言"无死锁"；spy 测试已覆盖核心保证。

## 流程 5：边界场景

- **空列表** `conflict_card_ids=[]`：`sorted([])` 返回 `[]`，循环不执行，主卡仍正常解冻（流程 1/2 的步骤 1-2、5-8 照常执行），不报错。AC-4。
- **单元素** `conflict_card_ids=[5]`：`sorted([5])=[5]`，循环执行 1 次，`get_card_with_lock` 调用顺序 == `[card_id, 5]`。AC-5。
- **已排序入参** `conflict_card_ids=[1,2,3]`：`sorted` 幂等，调用顺序不变。
- **含重复 ID** `conflict_card_ids=[2,1,2]`：`sorted=[1,2,2]`，循环对 id=2 加锁两次（第二次同事务内已持锁，PG 行锁不自锁，业务层重复处理同一卡计入 `failed_cards` 或 `cancelled_cards`——这是入参质量问题，本 Feature 保持原不去重语义不改业务行为，见 requirement U3）。

## 流程 6：跨层调用链（不变）

```
Router（不变，admin-unfreeze / batch-cancel 端点签名不变）
  → Service（仅加 sorted，不改方法签名 / 不改事务边界 / 不改状态机）
    → get_card_with_lock（不变，SELECT ... FOR UPDATE）
      → SQLAlchemy → PostgreSQL（不变，无 schema / migration 变更）
```

- Service / Repository / Router / schemas / OpenAPI 代码改动面：Service 三处各加 1 行 `sorted(...)`；其余零改动。
- 事务边界：仍由 Router `db.commit()` 统一提交，Service 不自行 commit。
- 租户隔离：`get_card_with_lock` 内 `WHERE tenant_id = :val`（[service.py:494-495](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L494-495)）保证租户隔离；`sorted` 不影响租户过滤语义。
- RBAC：端点不变，`@require_roles("admin", "super_admin")`（[router.py:305/467](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L305)）未动。
- 认证：`get_current_user` 未动，`tenant_id` / `operator_id` 仍来自已认证上下文。

## 流程 7：回归场景（排序不破坏既有行为）

- 既有 membership 测试（`test_cancel_schedule_rollback.py` 等）：排序仅改变 conflict 卡的处理顺序，不改变单卡处理逻辑、事务边界、状态机、流水生成 → 不影响既有用例的断言（断言通常针对单卡状态/余额/流水，不针对 conflict 列表内顺序）。
- F4.1 / F4.2 FK 测试：本 Feature 不动 DB schema / migration / order 模型 → 无影响。
- 租户隔离 / RBAC / 认证：均不涉及 Service `sorted` 改动 → 无影响。
- AI / MCP：`unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` 未被任何 MCP Tool 直接调用（grep `ai/` 无命中，见 UNKNOWN U1）→ 无影响。
