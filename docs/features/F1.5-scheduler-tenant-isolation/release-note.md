# F1.5 — Release Note

> Feature: 定时任务租户隔离
> 关闭日期：2026-09-26
> 状态：DONE

## Feature

APScheduler 定时任务按租户循环并设置 `tenant_id` ContextVar，确保定时任务不跨租户操作数据；单租户处理失败不影响其他租户。

## Problem

`tenant_query.py` 在 `get_tenant_id()` 为 `None` 时跳过租户过滤注入。定时任务运行在 APScheduler 线程，ContextVar 为空，导致对 `course_schedules`、`bookings`、`membership_cards` 等租户表全表扫描，跨租户操作数据。

涉及 6 个定时任务：
- schedule：`auto_finish_expired_schedules`、`auto_cancel_underbooked_schedules`
- membership：`auto_expire_membership_cards`、`auto_activate_membership_cards`、`notify_expiring_membership_cards`、`auto_unfreeze_membership_cards`

## Fix

最小补丁，2 个文件：

1. **每个 scheduler 函数开头查询所有 `status=ACTIVE` 的租户**（`Tenant` 模型无 `tenant_id` 字段，查询不受租户过滤影响）
2. **逐租户循环**：`set_tenant_id(tenant.id)` → 执行业务 → `finally: set_tenant_id(None)`
3. **异常隔离**：单租户业务异常被 `except Exception` 捕获并 `logger.exception` 记录，`continue` 处理下一租户
4. **每租户独立 `SessionLocal` 会话**，避免跨租户事务污染
5. 原有业务逻辑（状态流转、扣次、解冻等）逐行保留，仅外层加租户循环

## Files Changed

| 文件 | 改动 |
|------|------|
| `apps/api/src/app/modules/schedule/scheduler.py` | 2 个函数加租户循环 + 上下文 + 异常隔离；新增 `_get_active_tenants()` |
| `apps/api/src/app/modules/membership/scheduler.py` | 5 个函数加租户循环 + 上下文 + 异常隔离；新增 `_get_active_tenants()` |
| `apps/api/tests/test_scheduler_tenant_isolation.py` | 新建 9 个单元测试 |

## Tests

- `test_scheduler_tenant_isolation.py`：**9/9 通过**
  - 5 个测试验证各 scheduler 函数对每个租户调用 `set_tenant_id(tenant.id)`
  - 2 个测试验证单租户异常不中断后续租户（异常隔离）
  - 2 个测试验证无 ACTIVE 租户时直接返回
- py_compile：3 个文件全部通过
- 模块 import 冒烟：通过

## Acceptance

| AC | 判定 |
|----|------|
| AC-1 按租户循环 + set_tenant_id | ✅ PASS |
| AC-2 单租户异常隔离 | ✅ PASS |
| AC-3 上下文清理（finally set_tenant_id(None)） | ✅ PASS |
| AC-4 无 ACTIVE 租户直接返回 | ✅ PASS |
| AC-5 业务逻辑不变 | ✅ PASS |
| AC-6 变更范围 + py_compile + 无契约变更 | ✅ PASS |

Review 结论：**READY_FOR_ACCEPTANCE** → **CLOSE**。

## Known Risks

1. **真实多租户端到端隔离**：本 Feature 验证租户循环与异常隔离的结构正确性；真实数据隔离依赖 `tenant_query` ORM 事件注入（项目既有机制）。建议上线后观察日志中 `[租户{id}]` 前缀确认各租户独立处理。
2. **`_get_active_tenants` 重复实现**：schedule 和 membership 各一份，属基础设施查询；未来可下沉到 `TenantService` 统一。

## Release Notes

- 所有定时任务现在按 ACTIVE 租户循环处理，每个租户独立设置 `tenant_id` 上下文，确保只操作本租户数据，不再跨租户全表扫描。
- 单个租户处理失败（如 DB 异常）仅记录日志并跳过，不影响其他租户的定时任务执行。
- 原有业务逻辑（排期自动完成/取消、会员卡激活/过期/解冻/提醒）行为不变。
- 无 API 契约变更，四端前端无需改动。
