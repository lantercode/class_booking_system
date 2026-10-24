# F1.5 — 定时任务租户隔离 · Feature Review

> Feature ID：F1.5
> 评审日期：2026-09-26
> 评审性质：主 Agent 对照 AC 复核（单域后端修复）
> 评审输入：requirement.md / user-flow.md / acceptance.md / implementation-plan.md / implementation-report.md / static-verification.md / runtime-test-report.md + 独立源码核查

---

## Scope Review

**结论：严格遵守 F1.5 Scope。**

| 文件 | diff 实证 | 判定 |
|------|----------|------|
| `schedule/scheduler.py` | 新增 `_get_active_tenants()`；2 个函数外层加租户循环 + `set_tenant_id` + try/except/finally；日志加租户前缀 | ✅ 与 plan 一致 |
| `membership/scheduler.py` | 新增 `_get_active_tenants()`；5 个函数外层加租户循环 + `set_tenant_id` + try/except/finally；日志加租户前缀 | ✅ 与 plan 一致 |
| `tests/test_scheduler_tenant_isolation.py` | 新建，9 个单元测试，全 mock | ✅ 与 plan 一致 |

- 未修改 Service 层、Router 层、`main.py` 调度注册
- 未修改 `tenant_query.py` / `tenant_context.py` / `tenant_middleware.py`
- 未修改数据库结构、无 migration
- 未触碰工作区其他预存改动

## Architecture Review

**结论：符合架构规则，无违规。**

- **租户隔离**（`security/tenant-isolation.md`）：定时任务按租户循环，循环内 `set_tenant_id(tenant.id)`，使 `tenant_query` ORM 事件自动注入 `WHERE tenant_id = :val`。每租户独立 `SessionLocal` 会话，`finally` 清理上下文。符合"后台任务必须按租户循环、处理前 set_tenant_id"的要求。
- **分层**（`architecture/layering.md`）：scheduler 仅在外层加租户循环，业务逻辑仍走原有 Service（`schedule_service.cancel_schedule`）/ Repository，未绕过。
- **异常隔离**：单租户 `try/except Exception` + `logger.exception` + `continue`，不中断其他租户。
- **不重复业务逻辑**：原有业务逻辑逐行保留，`_get_active_tenants` 为基础设施查询（Tenant 无 tenant_id，非业务规则）。
- **不修改 Service/Router**：遵守约束。

## Code Review

**结论：最小修复，无隐藏业务逻辑变化。**

1. **`_get_active_tenants()`**：查询 `Tenant.status == ACTIVE`。`Tenant` 模型不含 `tenant_id` 字段，`tenant_query` 注入逻辑（`hasattr(entity, "tenant_id")`）不会对其生效，查询不会被误伤。
2. **租户循环结构**：`set_tenant_id(id)` → `try: ... except: continue finally: set_tenant_id(None)`。`finally` 保证上下文清理，即使业务抛异常。
3. **业务逻辑**：对比原代码，查询条件、状态流转、扣次/清零、解冻冲突检查、流水记录均逐行保留，仅缩进层级增加（移入 try 块）。
4. **日志**：增加 `[租户{tenant_id}]` 前缀，便于排查多租户问题，不影响功能。
5. **`auto_cancel_underbooked`**：`schedule_service.cancel_schedule` 调用保留，其内部查询因 `set_tenant_id` 生效而自动过滤租户，无需改动 Service。
6. 无顺手修复、无整文件格式化。

## Regression Review

**结论：回归风险低。**

- **业务逻辑**：原有状态流转、扣次、解冻逻辑未改，仅外层加循环。单元测试通过 mock 验证结构正确性。
- **任务注册**：`main.py` 未改，APScheduler 任务 ID、间隔不变。
- **`tenant_query` 机制**：未修改，既有租户过滤行为不变。
- **并发**：每租户独立会话 + 独立上下文，无跨租户事务污染。
- **空租户**：无 ACTIVE 租户时直接返回，行为安全。

## Acceptance Review

| AC | 判定 | 依据 |
|----|------|------|
| AC-1 按租户循环 + set_tenant_id | **PASS** | 5/5 单元测试 + 代码审查 |
| AC-2 单租户异常隔离 | **PASS** | 2/2 单元测试（bad/good session side_effect） |
| AC-3 上下文清理 | **PASS** | 代码审查 finally + 单元测试断言 None 调用 |
| AC-4 无 ACTIVE 租户直接返回 | **PASS** | 2/2 单元测试 |
| AC-5 业务逻辑不变 | **PASS** | diff 审查 + minimal-change-guard |
| AC-6 变更范围 + py_compile + 无契约变更 | **PASS** | git status + py_compile |

## Risks

| # | 风险 | 等级 | 处置建议 |
|---|------|------|---------|
| R1 | `_get_active_tenants` 在两个 scheduler 重复实现 | 低 | 基础设施查询，非业务逻辑；未来可下沉到 `TenantService.list_active_tenants()` 统一（需放开"不修改 Service"约束） |
| R2 | 真实多租户数据隔离未做端到端 DB 验证 | 中 | 本 Feature 验证租户循环与异常隔离的结构正确性；`tenant_query` ORM 注入机制为项目既有能力，已在 HTTP 请求链路验证。如需端到端验证，可构造多租户测试数据后手动触发任务 |
| R3 | `logger.exception` 在高并发失败场景下日志量增大 | 低 | 可接受，便于排查；失败本就是异常情况 |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 真实多租户数据端到端隔离效果 | 依赖 `tenant_query` 既有机制；建议生产灰度观察日志中 `[租户{id}]` 前缀是否符合预期 |

## Recommendation

1. **代码层面**：F1.5 修复正确、最小、完整。所有 scheduler 函数按租户循环 + 设置上下文 + 异常隔离，业务逻辑零回归。
2. **验收层面**：全部 AC 通过，可关闭。
3. **运维层面**：上线后观察定时任务日志，确认各租户独立处理、无跨租户数据操作。

**最终结论：READY_FOR_ACCEPTANCE**
