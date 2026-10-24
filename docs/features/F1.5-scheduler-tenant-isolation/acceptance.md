# F1.5 — Acceptance Criteria

> 每条可独立判定 PASS / FAIL。
> 主 AC 为 AC-1（租户循环 + 上下文设置）与 AC-2（异常隔离）；全部 AC 通过方可进入 REVIEW / ACCEPTANCE。

## AC-1 定时任务按租户循环并设置 ContextVar（主验收标准）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-1.1 | 每个 scheduler 函数先查询 `status=ACTIVE` 的租户列表 | 代码审查 + TC-01 |
| AC-1.2 | 循环内对每个租户调用 `set_tenant_id(tenant.id)` | TC-01 / TC-04 |
| AC-1.3 | 业务查询在 `set_tenant_id` 之后执行（使 `tenant_query` 注入过滤） | 代码审查 |
| AC-1.4 | 每个租户使用独立的 `SessionLocal` 会话 | 代码审查 |

## AC-2 单租户异常隔离（主验收标准）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-2.1 | 单个租户业务逻辑抛异常时，被 `except Exception` 捕获并 `logger.exception` 记录 | 代码审查 + TC-02 |
| AC-2.2 | 单租户异常后循环 `continue`，后续租户仍被处理 | TC-02 / TC-05 |
| AC-2.3 | 异常不向上传播（函数整体正常返回） | TC-02 |

## AC-3 上下文清理

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-3.1 | 每个租户处理完毕后 `finally` 中调用 `set_tenant_id(None)` | 代码审查 + TC-01 |
| AC-3.2 | 即使业务抛异常，`set_tenant_id(None)` 仍执行 | TC-02 |

## AC-4 边界：无 ACTIVE 租户

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-4.1 | 租户列表为空时函数直接返回，不调用 `set_tenant_id` | TC-03 / TC-09 |

## AC-5 业务逻辑不变

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-5.1 | 原有业务逻辑（查询条件、状态流转、扣次、解冻等）逐行保留，仅在外层加租户循环 | diff 审查 |
| AC-5.2 | 不修改 Service 层、Router 层、`main.py` 调度注册 | minimal-change-guard |
| AC-5.3 | 不修改 `tenant_query.py` / `tenant_context.py` | minimal-change-guard |

## AC-6 变更范围（静态）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-6.1 | 实际修改文件 ⊆ {schedule/scheduler.py, membership/scheduler.py} + 测试文件 | minimal-change-guard |
| AC-6.2 | 每个修改的 Python 文件通过 `python3 -m py_compile` | STATIC 记录 |
| AC-6.3 | 无 OpenAPI 契约变更（无 Router 改动） | 代码审查 |

## 判定规则

- 任何 AC-1.x / AC-2.x FAIL → Feature 整体 FAIL
- AC-3 ~ AC-6 中出现 FAIL → NEEDS_FIX 回到 DEVELOPMENT
