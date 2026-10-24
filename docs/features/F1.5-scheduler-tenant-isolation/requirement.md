# F1.5 — 定时任务租户隔离 · Requirement

> Feature ID：F1.5（Epic 1 / Phase 1 / P0）
> 阶段：REQUIREMENT（2026-09-26）

## Goal

APScheduler 定时任务按租户循环并设置 `tenant_id` ContextVar，确保定时任务不跨租户操作数据；单租户处理失败不影响其他租户。

## Problem

### P1：定时任务 ContextVar 为空导致跨租户操作（安全 / 数据隔离）

`app/core/tenant_query.py:40-45` 的 `_add_tenant_filter_to_orm_query` 逻辑：

```python
current_tenant_id = get_tenant_id()
if not current_tenant_id:
    return  # 无租户 ID 时跳过过滤注入
```

- HTTP 请求由 `tenant_middleware` 从请求头识别租户并 `set_tenant_id`，ContextVar 有值，租户过滤正常注入。
- **APScheduler 任务运行在独立线程 / 任务上下文，`get_tenant_id()` 返回 `None`**，`tenant_query` 跳过过滤注入。
- 结果：定时任务对 `course_schedules`、`bookings`、`membership_cards` 等租户表执行**全表扫描**，读到并修改**所有租户**的数据，违反多租户隔离。

### 涉及的定时任务

| 模块 | 函数 | 操作的租户表 |
|------|------|-------------|
| schedule | `auto_finish_expired_schedules` | `course_schedules`、`bookings` |
| schedule | `auto_cancel_underbooked_schedules` | `course_schedules`、`courses`、`course_types` + 调 `schedule_service.cancel_schedule` |
| membership | `auto_activate_membership_cards` | `membership_cards`、`membership_card_products`、`membership_card_transactions` |
| membership | `auto_expire_membership_cards` | `membership_cards`、`membership_card_transactions` |
| membership | `notify_expiring_membership_cards` | `membership_cards`（只读 + 日志） |
| membership | `auto_unfreeze_membership_cards` | `membership_cards`、`membership_card_freezes` |

## Scope

1. **T1.5.1**：每个 scheduler 函数开头查询所有 `TenantStatus.ACTIVE` 的租户
2. **T1.5.2**：循环内 `set_tenant_id(tenant.id)` 后再执行业务逻辑（使 `tenant_query` 自动注入租户过滤）
3. **T1.5.3**：异常隔离——单租户业务逻辑抛异常时仅记录日志并 `continue`，不中断其他租户；`finally` 中 `set_tenant_id(None)` 清理上下文

## Out of Scope

- 不修改 Service 层、Router 层
- 不修改 `main.py` 的调度器注册（任务注册、间隔不变）
- 不修改 `tenant_query.py` / `tenant_context.py` / `tenant_middleware.py`
- 不修改数据库结构
- 不引入新的定时任务或改变现有业务逻辑（状态流转、扣次、解冻等）
- 不涉及前端四端

## User Roles

系统自动任务，无直接用户角色。影响：所有租户的排期 / 会员卡状态变更由定时任务驱动，必须保证只操作本租户数据。

## Business Rules

1. 定时任务只能操作 `status=ACTIVE` 租户的数据
2. 每个租户独立处理：独立 `SessionLocal` 会话 + 独立 `set_tenant_id` 上下文
3. 单租户失败（DB 异常、业务异常等）必须被捕获并记录日志，**不得中断后续租户的处理**
4. 处理完毕后必须清理 `tenant_id` ContextVar（`set_tenant_id(None)`），避免污染后续同线程任务
5. 查询租户列表本身不受租户过滤影响（`Tenant` 模型无 `tenant_id` 字段，`tenant_query` 不会注入过滤）

## Dependencies

- `app/modules/tenant/models.py`：`Tenant` 模型、`TenantStatus.ACTIVE=1`
- `app/core/tenant_context.py`：`set_tenant_id(int)` / `get_tenant_id()`
- `app/core/database.py`：`SessionLocal`
- `app/core/tenant_query.py`：ORM 事件自动注入 `WHERE tenant_id = :val`

无前置 Feature。

## Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| `_get_active_tenants` 查询本身被租户过滤误伤 | 低 | `Tenant` 模型不含 `tenant_id` 字段，`tenant_query` 注入逻辑只对含 `tenant_id` 的实体生效，已确认 |
| 单租户异常未捕获导致整个任务中断 | 中 | 每个租户用 `try/except Exception` 包裹，`logger.exception` 记录后 `continue`；`finally` 清理上下文 |
| ContextVar 在 asyncio 任务间泄漏 | 低 | `AsyncIOScheduler` 每个 job 在独立 task 中运行，ContextVar 上下文隔离；且每租户 `finally` 主动 `set_tenant_id(None)` |
| 业务逻辑回归（原有状态流转被破坏） | 中 | 仅在外层加租户循环 + 上下文，原有业务代码逐行保留，通过单元测试 + py_compile 验证 |

## Acceptance Criteria（摘要）

- AC-1：每个 scheduler 函数先查询 ACTIVE 租户并逐租户 `set_tenant_id`
- AC-2：单租户抛异常不中断其他租户处理
- AC-3：处理完毕后 `set_tenant_id(None)` 清理上下文
- AC-4：无 ACTIVE 租户时函数直接返回，不调用 `set_tenant_id`
- AC-5：原有业务逻辑不变，仅增加租户循环层
