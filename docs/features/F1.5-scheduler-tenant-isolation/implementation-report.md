# F1.5 — Implementation Report

> Feature: F1.5 定时任务租户隔离
> 阶段：DEVELOPMENT → STATIC VERIFICATION → TESTING 完成
> 日期：2026-09-26

## Changed Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/modules/schedule/scheduler.py` | 2 个函数外层加租户循环 + `set_tenant_id` + try/except/finally 异常隔离；新增 `_get_active_tenants()` |
| 2 | `apps/api/src/app/modules/membership/scheduler.py` | 5 个函数外层加租户循环 + `set_tenant_id` + try/except/finally 异常隔离；新增 `_get_active_tenants()` |
| 3 | `apps/api/tests/test_scheduler_tenant_isolation.py`（新建） | 9 个单元测试 |

## Exact Changes

### 共用模式

每个 scheduler 函数统一改造为：

```python
async def some_scheduler_task():
    # （保留原 enabled 开关）

    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                # ===== 原有业务逻辑逐行保留 =====
                ...
                await db.commit()
        except Exception as e:
            logger.exception(f"[定时任务][租户{tenant_id}] ...失败，已跳过该租户: {e}")
            continue
        finally:
            set_tenant_id(None)
```

### `_get_active_tenants()`

```python
async def _get_active_tenants():
    async with SessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE.value)
        )
        return result.scalars().all()
```

`Tenant` 模型不含 `tenant_id` 字段，`tenant_query` 自动注入不会过滤此查询。

### schedule/scheduler.py

- `auto_finish_expired_schedules()`：保留 `AUTO_FINISH_ENABLED` 开关；原过期排期 + 预约状态流转逻辑移入 try 块
- `auto_cancel_underbooked_schedules()`：保留 `AUTO_CANCEL_UNDERBOOKED_ENABLED` 开关；原 join 查询 + `cancel_schedule` 逻辑移入 try 块
- 日志前缀统一增加 `[租户{tenant_id}]`

### membership/scheduler.py

- `auto_expire_membership_cards()`：原过期卡处理逻辑移入 try 块
- `auto_activate_membership_cards()`：`_expire_cards_in_transaction` 调用保留；原激活 + 冲突检查逻辑移入 try 块
- `notify_expiring_membership_cards()`：原提醒逻辑移入 try 块（无 commit）
- `auto_unfreeze_membership_cards()`：原解冻 + 冲突处理逻辑移入 try 块；`MembershipCardRepository` import 位置不变

## Scope Verification

- 实际修改文件 ⊆ {schedule/scheduler.py, membership/scheduler.py} + 1 测试文件
- 未修改 Service 层、Router 层、`main.py` 调度注册
- 未修改 `tenant_query.py` / `tenant_context.py` / `tenant_middleware.py`
- 未修改数据库结构
- 未触碰工作区其他预存改动

## Tests Run

| 套件 | 结果 | 说明 |
|------|------|------|
| `test_scheduler_tenant_isolation.py` | ✅ 9 passed | 租户循环、set_tenant_id 调用序列、异常隔离、空租户边界 |
| py_compile（3 文件） | ✅ 全部通过 | schedule/scheduler.py、membership/scheduler.py、test 文件 |
| 模块 import 冒烟 | ✅ OK | 两个 scheduler 模块正常 import，函数签名不变 |

## Results

- **AC-1（主验收）PASS**：每个 scheduler 函数查询 ACTIVE 租户并逐租户 `set_tenant_id`，业务查询在上下文设置后执行
- **AC-2（主验收）PASS**：单租户异常被捕获记录，后续租户继续处理，函数整体不抛出
- **AC-3 PASS**：`finally: set_tenant_id(None)` 在每租户处理后执行，含异常场景
- **AC-4 PASS**：无 ACTIVE 租户时直接返回，不调用 `set_tenant_id`
- **AC-5 PASS**：原有业务逻辑逐行保留，仅外层加租户循环
- **AC-6 PASS**：变更范围 ⊆ 白名单，py_compile 通过，无 OpenAPI 变更

## Risks

1. **`_get_active_tenants` 重复实现**：schedule 和 membership 两个 scheduler 各定义一份相同的 `_get_active_tenants`。属于基础设施查询（非业务逻辑），且约束"不修改 Service 层"，接受轻度重复。未来可考虑下沉到 `TenantService.list_active_tenants()` 统一。
2. **ContextVar 清理**：依赖 `finally` 保证清理；AsyncIOScheduler 每 job 独立 task，上下文天然隔离，无泄漏风险。
3. **日志量增加**：每租户日志前缀增加 `[租户{id}]`，便于排查，不影响功能。

## UNKNOWN

- 无。

## Handoff

- 执行 Agent：backend-engineer（单一）
- 下一阶段：REVIEW → ACCEPTANCE → CLOSE
- 验收入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/test_scheduler_tenant_isolation.py -v`
