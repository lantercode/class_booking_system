---
alwaysApply: true
---

复杂任务开始前，
读取 docs/ai/workflows/multi-agent-collaboration-v3.md，
并按照其中定义的 Agent Selection、Handoff、
Reconciliation、Testing、Review 执行。

# Multi-Agent Orchestration

当前项目存在以下专业智能体：

- project-architect
- frontend-engineer
- backend-engineer
- database-engineer
- mcp-engineer

## 1. 总体职责

当前内置 Agent 作为项目开发总控。

不要默认亲自完成所有任务。

根据任务复杂度选择合适的专业 Agent。

---

## 2. Agent Selection

简单单领域任务：

直接处理，不必强制调用 Architect。

前端任务：
优先 frontend-engineer。

后端任务：
优先 backend-engineer。

数据库任务：
优先 database-engineer。

MCP / Tool 任务：
优先 mcp-engineer。

复杂跨模块任务：
优先 project-architect。

---

## 3. Complex Feature Workflow

复杂任务优先执行：

Analyze
→ Architect
→ Specialist Analysis
→ Reconcile
→ Implement
→ Test
→ Review

---

## 4. Architect

对于复杂跨模块任务：

先调用 project-architect。

Architect 负责：

- 需求理解
- 架构分析
- 技术方案
- 任务拆分
- Agent Selection
- 依赖识别
- 冲突识别

Architect 不应无必要直接修改业务代码。

---

## 5. Specialist Agents

根据 Architect 方案选择：

Frontend:
frontend-engineer

Backend:
backend-engineer

Database:
database-engineer

MCP:
mcp-engineer

只调用与当前任务真正相关的 Agent。

不要无条件调用全部 Agent。

---

## 6. Context

所有 Agent 必须遵守当前项目 `.trae/rules/`。

优先阅读：

- 当前项目架构
- 当前 Feature 文档
- docs/ai/workflows/
- docs/ai/architecture/
- docs/ai/implementation/

禁止根据假设替代真实代码调查。

---

## 7. Handoff

Agent 完成任务后，应返回：

- Analysis
- Decision
- Changed Files
- Dependencies
- Risks
- UNKNOWN
- Handoff

后续 Agent 应消费前一个 Agent 的结果。

禁止重复进行已经完成的无意义分析。

---

## 8. Conflict Reconciliation

如果不同 Agent 的方案发生冲突：

记录：

- Conflict
- Evidence
- Impact
- Recommendation

由主 Agent 进行 Reconciliation。

不要静默选择其中一个方案。

---

## 9. Architecture Boundaries

遵守项目现有架构规则。

尤其：

Frontend
→ API
→ Backend Service
→ Repository
→ Database

MCP
→ Service
→ Repository
→ Database

禁止：

MCP
→ Database

禁止重复实现已有业务逻辑。

---

## 10. Safety

不要让多个 Agent 无序修改同一文件。

修改前确认：

- Scope
- Dependencies
- Existing Changes

禁止覆盖用户未提交修改。

禁止执行 destructive Git 操作。

---

## 11. Verification

完成开发后：

Test
→ Review

至少确认：

- 功能
- API
- Security
- Tenant Isolation
- Transaction
- Regression

---

## 12. Collaboration Workflow

如果存在：

docs/ai/workflows/multi-agent-collaboration-v3.md

复杂任务开始前读取该文档，
并遵守其中定义的：

- Agent Selection
- Handoff
- Reconciliation
- Artifact
- Testing
- Review

该 Workflow 是团队协作流程，
不要将其内容重复复制到本 Rule 中。

---

## 附录 A：风险分级与 Agent 选择矩阵（M1/M2，2026-10-24 批准）

> 引用型补充规则。完整定义见 `docs/engineering/ai-coding-optimization-plan.md` §3–§5 与实验报告 `docs/engineering/ai-coding-efficiency-experiment-1.md`。本附录不替代上文 §1–§12，仅在其基础上增加分级与选择口径。

### 风险分级（开工时声明）

| 等级 | 定义 | 典型任务 |
|------|------|---------|
| L1 | 文案/常量/注释等零行为改动 | 改错别字、调整日志文案 |
| L2 | 单文件、单域、无跨层依赖 | 前端展示调整、纯工具函数 |
| L3 | 单域特性，涉及多文件但不改核心状态机 | 只读查询端点、列表筛选 |
| L4 | 跨模块/核心状态机/事务/并发/鉴权 | 预约扣次、改派、发卡、租户隔离 |

### 产物策略

- L1/L2：可用扩展版 `task-record.md` 替代 9 份 Feature 产物，仍须保留 diff、测试日志、人工验收证据。
- L3/L4：9 份产物齐全。

### Agent 选择矩阵（M2）

| 等级 | 必调 | 可选 | 说明 |
|------|------|------|------|
| L1 | 主 Agent | — | 不调专业 Agent |
| L2 | 对应域 Agent | — | 单域；Review 由主 Agent 自查替代 architect |
| L3 | 对应域 Agent + architect（规划/复核） | database-engineer（仅当有 DB 结构变更） | |
| L4 | architect + 全部相关域 Agent | — | 并发场景须含并发专项测试 |

> No DB change 时 L3 可不调 database-engineer，但须在计划中注明「No DB change（已核对）」。

---

## 附录 B：上下文分层读取（M3，2026-10-24 批准）

> 引用型补充规则。与上文 §6 Context 配合执行。

- **常驻规则不重复全量读取**：`.trae/rules/` 已在系统上下文中，不在任务内重复 `cat` 全文。
- **代码按需区段读取**：根据需求定位文件与行号后读取区段（如 `service.py` 的相关方法），不做全仓扫描。
- **任务记录第 7 节登记**：实际读取的文件清单、范围与行数，用于事后审查是否过度加载。
