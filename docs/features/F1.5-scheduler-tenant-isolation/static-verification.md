# F1.5 — Static Verification

> 阶段：STATIC VERIFICATION
> 日期：2026-09-26

## 1. 范围守卫（minimal-change-guard）

### 1.1 白名单

```
apps/api/src/app/modules/schedule/scheduler.py
apps/api/src/app/modules/membership/scheduler.py
apps/api/tests/test_scheduler_tenant_isolation.py（新建）
```

### 1.2 范围复核结论

- ✅ 2 个修改文件 + 1 个新建测试文件均在 `git status` 中
- ✅ 白名单外，F1.5 相关目录无其他文件被修改
- ✅ 未修改 Service 层、Router 层、`main.py`、`tenant_query.py`、`tenant_context.py`

### 1.3 逐文件改动摘要

- **schedule/scheduler.py**：新增 `_get_active_tenants()`；`auto_finish_expired_schedules` 与 `auto_cancel_underbooked_schedules` 外层包租户循环 + `set_tenant_id` + try/except/finally；日志前缀加租户 ID
- **membership/scheduler.py**：新增 `_get_active_tenants()`；5 个函数外层包租户循环 + `set_tenant_id` + try/except/finally；日志前缀加租户 ID
- **test_scheduler_tenant_isolation.py**：新建，9 个单元测试（mock `_get_active_tenants` / `SessionLocal` / `set_tenant_id`）

## 2. 编译验证

| 文件 | py_compile |
|------|-----------|
| `modules/schedule/scheduler.py` | ✅ OK |
| `modules/membership/scheduler.py` | ✅ OK |
| `tests/test_scheduler_tenant_isolation.py` | ✅ OK |

## 3. 契约验证（AC-6.3）

- 无 Router 层改动 → 无新端点、无删除端点、无 DTO 变更
- 无 OpenAPI 契约变更
- `main.py` 调度器注册未改 → 任务 ID、间隔不变

## 4. 架构合规验证

| 规则 | 判定 | 依据 |
|------|------|------|
| 定时任务补齐租户上下文（`security/tenant-isolation.md`） | ✅ | 每租户 `set_tenant_id(tenant.id)` |
| 单租户失败不影响其他租户 | ✅ | `try/except Exception` + `continue` |
| 不绕过 Service 层 | ✅ | 原有 `schedule_service.cancel_schedule` 调用保留；未直接操作其他模块 Repository |
| 不修改数据库结构 | ✅ | 无 migration / model 改动 |
| 不重复业务逻辑 | ✅ | 原有业务逻辑逐行保留，仅外层加循环；`_get_active_tenants` 为基础设施查询 |

## 5. 静态结论

| AC | 判定 |
|----|------|
| AC-6.1 变更范围 ⊆ 白名单 | ✅ PASS |
| AC-6.2 py_compile | ✅ PASS |
| AC-6.3 无 OpenAPI 契约变更 | ✅ PASS |
