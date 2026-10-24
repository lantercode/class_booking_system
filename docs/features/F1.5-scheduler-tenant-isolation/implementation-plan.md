# F1.5 — 定时任务租户隔离 · 实施方案

> Feature ID：F1.5
> 日期：2026-09-26
> 性质：最小补丁（2 文件 + 1 测试），仅在外层加租户循环 + 上下文设置 + 异常隔离
> 关联文档：[requirement.md](./requirement.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

`app/core/tenant_query.py:40-45`：

```python
current_tenant_id = get_tenant_id()
if not current_tenant_id:
    return  # ContextVar 为空时跳过租户过滤注入
```

定时任务运行在 APScheduler 线程，`tenant_context.get_tenant_id()` 返回 `None`，导致 `tenant_query` 不为租户表查询注入 `WHERE tenant_id = :val`，定时任务全表扫描并跨租户操作数据。

---

## Affected Files

| # | 文件 | 改动内容 |
|---|------|---------|
| 1 | `apps/api/src/app/modules/schedule/scheduler.py` | 2 个函数加租户循环 + `set_tenant_id` + 异常隔离；新增 `_get_active_tenants()` 辅助函数 |
| 2 | `apps/api/src/app/modules/membership/scheduler.py` | 5 个函数加租户循环 + `set_tenant_id` + 异常隔离；新增 `_get_active_tenants()` 辅助函数 |
| 3 | `apps/api/tests/test_scheduler_tenant_isolation.py`（新建） | 9 个单元测试 |

---

## 共用模式

每个 scheduler 函数统一改造为以下结构：

```python
async def some_scheduler_task():
    # （保留原有的 enabled 开关检查，如 AUTO_FINISH_ENABLED）

    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                # ===== 原有业务逻辑（逐行保留）=====
                ...
                await db.commit()
                logger.info(...)
        except Exception as e:
            logger.exception(f"[定时任务][租户{tenant_id}] ...失败，已跳过该租户: {e}")
            continue
        finally:
            set_tenant_id(None)
```

### `_get_active_tenants()` 辅助函数

```python
async def _get_active_tenants():
    async with SessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE.value)
        )
        return result.scalars().all()
```

**关键说明**：`Tenant` 模型（`modules/tenant/models.py`）继承 `Base, TimestampMixin`，**不含 `TenantMixin`**，因此没有 `tenant_id` 字段。`tenant_query._add_tenant_filter_to_orm_query` 只对含 `tenant_id` 属性的实体注入过滤，查询 `tenants` 表不会被误伤，无需担心被当前 ContextVar 过滤。

---

## 逐函数改动要点

### schedule/scheduler.py

#### 1. `auto_finish_expired_schedules()`

- 保留 `if not settings.AUTO_FINISH_ENABLED: return` 开关
- 外层包租户循环
- 原业务逻辑（查询过期排期 → 更新排期状态 → 更新预约状态 → commit）完整移入 `try` 块
- 日志前缀增加 `[租户{tenant_id}]` 标识

#### 2. `auto_cancel_underbooked_schedules()`

- 保留 `AUTO_CANCEL_UNDERBOOKED_ENABLED` 开关
- 外层包租户循环
- 原业务逻辑（join 查询 → 循环调 `schedule_service.cancel_schedule` → commit）完整移入 `try` 块
- 注意：`schedule_service.cancel_schedule` 内部的查询也会因 `set_tenant_id` 生效而自动过滤租户

### membership/scheduler.py

#### 3. `auto_expire_membership_cards()`

- 无 enabled 开关，直接查询租户
- 原业务逻辑（查询过期卡 → 次卡清零 → 状态改 EXPIRED → 流水 → commit）完整移入 `try` 块

#### 4. `auto_activate_membership_cards()`

- 外层包租户循环
- `_expire_cards_in_transaction(db, now)` 调用保留（在同一会话内，已设置租户上下文）
- 原激活逻辑（冲突检查 → ACTIVE → 计算到期日 → 流水 → commit）完整移入 `try` 块

#### 5. `notify_expiring_membership_cards()`

- 外层包租户循环
- 原提醒逻辑完整移入 `try` 块
- 此函数无 commit（只读 + 日志），但仍用 `try/except/finally` 保证异常隔离与上下文清理

#### 6. `auto_unfreeze_membership_cards()`

- `MembershipCardRepository` 的 import 保留在函数内（原代码位置）
- 外层包租户循环
- 原解冻逻辑（冲突检查 → 解冻 / 更新原因 → 冻结记录 → commit）完整移入 `try` 块

---

## Why This Fix Is Sufficient

1. **租户过滤自动生效**：`set_tenant_id(tenant.id)` 后，`tenant_query` 的 `do_orm_execute` 事件在所有 ORM 查询执行前自动注入 `WHERE tenant_id = :id`，无需修改业务 SQL。
2. **租户列表查询不受影响**：`Tenant` 无 `tenant_id` 字段，查询 `tenants` 表不会被过滤。
3. **异常隔离**：每租户 `try/except Exception` + `continue`，单租户失败不影响其他租户。
4. **上下文清理**：`finally: set_tenant_id(None)` 保证 ContextVar 不污染后续任务。
5. **业务零回归**：原有业务逻辑逐行保留，仅在外层加循环与上下文，不改变任何状态流转、扣次、解冻规则。

---

## Verification Plan

| AC 编号 | 验证方式 |
|---------|---------|
| AC-1.1 ~ AC-1.4 | 代码审查 + 单元测试（mock `_get_active_tenants` 多租户，断言 `set_tenant_id` 调用序列） |
| AC-2.1 ~ AC-2.3 | 单元测试（第一个租户 session.execute 抛异常，断言第二个租户仍被处理） |
| AC-3.1 ~ AC-3.2 | 代码审查 `finally` 块 + 单元测试断言 `set_tenant_id(None)` 调用 |
| AC-4.1 | 单元测试（mock 空租户列表，断言 `set_tenant_id` 未被调用） |
| AC-5.1 ~ AC-5.3 | git diff 审查 + minimal-change-guard |
| AC-6.1 ~ AC-6.3 | git diff + py_compile |

---

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | `_get_active_tenants` 是否应复用 TenantService | TenantService 当前无 `list_active_tenants` 方法，且约束"不修改 Service 层"，故在 scheduler 内直接查询；Tenant 无 tenant_id 不受过滤影响 |
| U2 | ContextVar 在 AsyncIOScheduler 多 job 并发时是否互相干扰 | `AsyncIOScheduler` 每个 job 在独立 asyncio task 运行，ContextVar 上下文复制隔离；且每租户 finally 主动清理，无干扰 |
