---
alwaysApply: false
globs: "apps/api/**/*.py"
---

# 后端测试规范

测试框架：pytest，目录 `apps/api/tests/`（`unit/`、`integration/`）。命令：`uv run pytest`（根目录 `pnpm` 也会编排）。

## 必须有测试的场景

- 新增/修改重要业务逻辑（预约、取消、扣次/回补、发卡、冻结/解冻、状态流转）。
- 修复任何业务 Bug 必须同时补回归测试，禁止只改实现不补测试。
- 新增 / 修改 MCP Tool、意图识别、AgentRuntime 行为必须补对应用例（参考既有 `test_mcp_server.py`、`test_agent_runtime.py`、`test_multi_turn_booking.py`）。

## 集成测试约束

- 集成测试使用**真实 Uvicorn 服务（端口 8765，后台线程）+ 真实 PostgreSQL + 真实 Redis，不 mock**。
- 依赖 `pnpm db:up` 提供的基础设施；每会话创建全新 schema。
- **禁止**改回进程内 in-process test client：会与 asyncpg 事件循环冲突（既有 `conftest.py` 的方案是踩坑后的结论）。

## 必测专项

- **并发一致性**：并发抢名额（SKIP LOCKED）、重复提交取消（FOR UPDATE + 状态重检）、会员卡扣次/回补、并发发卡冲突检查。
- **事务原子性**：下游写失败时上游写入必须回滚。
- **多租户隔离**：跨租户访问必须为空/403。
- **认证/RBAC**：未登录、无权限、Token 黑名单场景。
- **MCP/AI**：四关校验、非法入参、Service 异常被友好捕获、Prompt Injection 基本用例。

## CI 对齐

CI（`.github/workflows/ci.yml`）执行：Ruff lint → Mypy → `alembic upgrade head` → `pytest tests/unit`。本地提交前至少跑通 lint 与相关测试；Mypy 当前 CI 为非阻塞，但新代码不应引入新的类型错误。

---

## 附录：按风险分级裁剪测试范围（M5，2026-10-24 批准）

> 引用型补充规则。完整定义见 `docs/engineering/ai-coding-optimization-plan.md` §6 与实验报告 `docs/engineering/ai-coding-efficiency-experiment-1.md`。不替代上文「必须有测试的场景」与「必测专项」。

| 等级 | 单元 | 集成 | 并发专项 | 定向回归 |
|------|------|------|---------|---------|
| L1 | — | — | — | — |
| L2 | 改动函数级（如有） | — | — | 改动域冒烟 |
| L3 | 改动逻辑全覆盖 | 主流程 + 边界 | 仅涉并发时 | 改动域 |
| L4 | 全覆盖 | 全覆盖 | **必测（不可裁剪）** | 改动域 + 关联域 |

**保留项（任何等级不可裁剪）**：并发一致性、事务原子性、多租户隔离、认证/RBAC——只要任务涉及即必须测试。

