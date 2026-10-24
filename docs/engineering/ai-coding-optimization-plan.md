# AI Coding 开发效率优化方案（提案）

> 日期：2026-10-21
> 状态：**提案 / 未实施**。本文件不修改任何 Rules、Skills、业务代码或 CI 配置；实施需人工逐项批准。
> 上游依据：`docs/engineering/ai-coding-efficiency-audit.md`（问题编号 P1–P7、假设 H1–H4）
> 原则：不删除任何业务规则、权限检查、租户隔离与必要测试；不重写 Harness；不新增 Agent / Skill / MCP；不声称未实测的性能提升。

---

## 0. 设计边界

**只做四类调整**
1. **路由**：任务按风险分级，决定走多重流程（M1）。
2. **编排**：按范围决定谁参与、哪些步骤可并行（M2、M7）。
3. **上下文**：区分"必须常驻 / 按需读取 / 禁止全量读取"（M3、M4）。
4. **度量**：让耗时与返工可被记录（M5、M6）。

**明确不做**
- 不删减 `.trae/rules/` 中的安全、权限、租户、事务、契约条款。
- 不降低 L3/L4 的验证与人工验收要求。
- 不新增角色；不把流程判断交给模型"自觉"。
- 不允许 Agent 自证任务通过。

---

## 1. M1｜L1–L4 任务风险分级与动态工作流

### 1.1 分级定义

| 等级 | 判定条件（全部满足） | 流程 | 产物 | 验证 |
|------|---------------------|------|------|------|
| **L1 微改** | ≤1 个文件；不涉及业务规则/状态机/事务/权限/租户/契约；可静态判定 | 直接实施 → 自检 | `task-record.md`（简短） | 目标文件编译/类型检查 + 相关断言脚本 |
| **L2 小修** | ≤3 个文件；单一模块；不改 API 契约、不改表结构；有既有测试可复用 | 领域 Agent → 实施 → 定向验证 | `task-record.md` + 测试证据 | 编译 + 受影响模块的单测 + diff 白名单 |
| **L3 单域特性** | 多文件但单一领域；可能新增端点/页面（不改表结构） | 精简生命周期：REQUIREMENT 合并 FLOW/AC → DESIGN 对账 → 实施 → 静态 → 运行时（按 AC）→ Review | requirement/acceptance/implementation-plan/report/static/review（6 份，可合并空白节） | 单测 + 契约核对 + 前端构建（如涉及） |
| **L4 跨域/高风险** | 跨模块；或涉及数据库迁移、认证授权、租户隔离、事务并发、支付、AI 写操作、对外契约破坏性变更 | **完整** lifecycle 0–12 + architect + 四方 Review + 人工验收 | 现有 9 份不变 | 全量分层测试 + 并发 + 租户隔离 + 人工验收 |

### 1.2 判定规则（必须先声明，后开工）

- 任务开始时输出一行：`RISK_LEVEL: Lx | 理由 | 涉及域 | 预期文件清单`。
- **只升不降**：实施中发现触达新域（如碰到迁移、权限装饰器、租户查询），立即升级并补流程。
- **硬性升级触发器**（任一命中即 ≥L3，命中两项即 L4）：
  1. 修改 `apps/api/src/app/core/`（安全/RBAC）或任何 `*_middleware*`
  2. 新增/修改 Alembic 迁移或模型字段
  3. 修改 MCP Tool / AgentRuntime / 写操作链路
  4. 删除或改语义的 API 字段/端点
  5. 任何 `TenantAwareRepository` 之外的裸查询
  6. 并发/锁/事务边界变更

### 1.3 与现有规则的关系

- `orchestration.md` "简单单领域任务：直接处理" 与 L1/L2 一致，本方案只是把它**可判定化**（用文件数与触发器替代主观判断）。
- L4 完全沿用现有 lifecycle 与 v3，不减任何环节。

**对应审计问题**：P2（产物量）、P3（验证强度）、P4（重复读取）。

---

## 2. M2｜按任务范围选择 Agent

### 2.1 选择矩阵（替代"默认全上"）

| 触达范围 | 必须参与 | 明确不参与 | 备注 |
|---------|---------|-----------|------|
| 仅 `apps/api/src/app/modules/<one>/` 内部、无契约变更 | backend-engineer | architect / frontend / database / mcp | L1/L2 可由主 Agent 直接做 |
| 仅前端一个 App 的页面/样式 | frontend-engineer | architect / backend / database / mcp | 契约只读核对 |
| 新增/改表结构 | database-engineer + backend-engineer | frontend（除非同时改 UI） | 迁移与代码同批 |
| 改 `ai/mcp_server.py`、Tool、Runtime | mcp-engineer（+ backend 补 Service） | frontend（契约未变时） | 引用 v3 §5 铁律 4 |
| 跨 ≥2 域或触达契约 | project-architect + 对应域 Agent | 无关域 | architect 只编排不写业务代码 |

### 2.2 空转约束

- 每次任务结束在 `task-record.md` 记录：`invoked_agents` 与 `not_invoked_reason`。
- 判断标准：**没有该域文件的写入或只读验证需求，就不调用该域 Agent**。
- 与 v3 R4（Database 即使 No Change 也要给 `[NEW]`）的冲突：仅在 L4 保留；L3 及以下如无表结构变更，database-engineer 不参与，改为 architect 在计划中记录"No DB change（已核对）"。**该项需人工批准后才生效**（属于对现有固化规则的调整）。

**对应审计问题**：P4、H2。

---

## 3. M3｜上下文加载分层

### 3.1 三层读取策略

| 层级 | 内容 | 何时加载 | 现状对照 |
|------|------|---------|---------|
| **T0 常驻（不变量）** | 安全/权限/租户/分层/契约的核心约束，压缩为"规则索引 + 关键禁令清单"（目标 ≤120 行） | 始终 | 当前 9 条 alwaysApply 约 483 行 |
| **T1 任务域（按 glob）** | `backend/fastapi.md`、`database/*`、`frontend/*`、`testing.md` 等 | 按修改文件路径自动加载 | 已存在 glob，但常被全量通读 |
| **T2 按需（查目录再读节）** | v3 协议、lifecycle SKILL、Feature 设计文档、原型 | 仅读被引用的小节，不整篇读 | 现在常整篇读完 461 行 v3 / 9 份产物 |

### 3.2 必读清单（按等级）

| 等级 | 必读 | 禁止 |
|------|------|------|
| L1 | 目标文件 + T0 索引 + 对应 T1 规则 | 不读 v3 / lifecycle 全文 / Feature 设计文档 |
| L2 | 上述 + 该模块现有测试 1 份 + `testing.md` | 不读无关 Feature 目录 |
| L3 | + lifecycle 对应阶段章节（按节读取）+ 1 份最接近的样板 Feature | 不通读全部 9 份产物 |
| L4 | + v3 全文（仅此级别） | — |

### 3.3 大文件处理

- 单文件 > 64KB（如原型 `index.html` 190KB / 87KB）禁止反复整篇读取：先读目录/锚点，再用定向检索取段；把"已读区段"记入任务记录，避免同段重复读。
- Feature 文档 > 500 行（F6.0 有 6 份）先读标题结构，再按需取节。

**对应审计问题**：P1、P2、P4。

---

## 4. M4｜Rules / Skills / 任务提示词 / 调度器职责边界

### 4.1 职责定义（单一来源）

| 载体 | 只回答 | 不得包含 | 加载方式 |
|------|--------|---------|---------|
| **Rule** | "什么必须成立"（不变量、禁令、契约） | 步骤流程、阶段编号、产物模板 | 常驻或按 glob |
| **Skill** | "按什么步骤完成 + 产物模板 + 判定" | 重复抄写 Rule 原文 | 按任务类型调用 |
| **任务提示词** | 本次任务的范围、验收、文件白名单 | 通用流程复述 | 每任务一次 |
| **调度器（主 Agent）** | 分级、选 Agent、并行编排、冲突仲裁 | 代替 Specialist 做专业结论 | 始终 |

### 4.2 去重映射（建议，需批准后执行）

| 重复内容 | 建议单一来源 | 其他位置处理 |
|---------|-------------|-------------|
| Agent Selection / Handoff / Reconciliation | `multi-agent-collaboration-v3.md` | `orchestration.md` 改为 1 段引用 + 分级触发器 |
| 阶段编号 | `feature-delivery-lifecycle/SKILL.md` | v3 只描述协作关系，不再给 Phase 0–8 全流程编号（或明确"v3 Phase = 协作阶段，映射见 S1"） |
| 测试分层 | 新增到 `testing.md` 的决策表 | lifecycle Stage 9 只引用，不重复列举 |
| 最小改动核对命令 | `minimal-change-guard` 脚本 | SKILL 与 lifecycle 只引用脚本路径 |

> 注意：这属于**修改现有 Rules/Skills**，未经人工批准不得执行；本方案只给出映射。

**对应审计问题**：P1。

---

## 5. M5｜按风险分层测试

### 5.1 测试层级决策表

| 改动类型 | 必跑 | 条件触发 | 不跑 |
|---------|------|---------|------|
| 纯文案/样式/原型 | 目标端构建或断言脚本 | 视觉交互改动 → 人工点检清单 | 后端 pytest |
| 单模块业务逻辑（无事务/并发） | `py_compile` + 该模块单测 | 改状态机 → 加集成用例 | 全量 integration |
| 事务/扣次/回补/锁 | 定向单测 + 集成（真实 PG/Redis） | 并发路径 → 并发回归 | 无关模块 integration |
| 权限/租户 | 对应 RBAC/租户集成用例 | 新端点 → 403 矩阵 | 全量前端构建 |
| 契约变更 | OpenAPI 生成 + `gen:types` + 受影响端构建 | 破坏性变更 → 四端影响面核对 | — |
| 迁移 | `alembic upgrade head` + 回滚脚本演练 | 存量数据 → 只读审计 | — |

### 5.2 保留项（不可优化掉）

- 集成测试仍用真实 Uvicorn + 真实 PG/Redis，禁止改回 in-process client（`testing.md` 结论）。
- 并发一致性、事务原子性、租户隔离、认证/RBAC 四类专项保留。
- 人工验收与运行时证据保留；Agent 不得仅凭自述判 PASS。

### 5.3 与 CI 的关系

- CI 保持现状（Ruff → Mypy 非阻塞 → 迁移 → unit）；**不删任何 job**。
- 建议新增（需批准）：按改动路径选择测试的说明文档，而不是改 CI 逻辑；先观察 4 个任务再决定是否引入 `paths` 过滤。

**对应审计问题**：P3。

---

## 6. M6｜任务遥测与指标

### 6.1 记录载体

每个任务在 Feature 目录（或 L1/L2 的 `docs/engineering/task-records/`）新增一份 `task-record.md`，固定字段：

```markdown
- task_id / feature_id / risk_level / start_at / end_at / wall_clock
- stages: [ {name, start, end, agent, tool_calls, notes} ]
- files_expected / files_actual / scope_pass
- handoffs: [ {from, to, package, missing_items} ]
- rework: [ {stage, reason, count} ]
- verification: { static, unit, integration, runtime, human }
- outcome: PASS / FAIL / BLOCKED
- context: { docs_read: [path#section], lines_read }
```

L1/L2 可只保留前 7 项；不要求写长篇叙述。

### 6.2 指标定义

| 指标 | 定义 | 数据来源 |
|------|------|---------|
| Lead Time | `end_at - start_at` | task-record |
| Stage Time | 各阶段耗时 | task-record |
| Tool Time | 脚本/测试/构建耗时 | 命令计时 |
| Rework Rate | NEEDS_FIX 或需求反转次数 / 任务数 | task-record + review |
| First-pass Acceptance | 首次人工验收通过比例 | acceptance 记录 |
| Doc Ratio | 产出 md 行数 / 变更代码行数 | `wc -l` + `git diff --numstat` |
| Agent Efficiency | 有实质产出的 Agent 调用 / 总调用 | invoked_agents |
| Context Load | 读取文档行数 | context 字段 |

### 6.3 采集方式

- 不新建工具；用现有 Shell 的 `time`、`git diff --numstat`、`wc -l` 手工/脚本写入。
- 如后续需要，可加一个只读汇总脚本（**需单独批准，不在本方案自动实施**）。

**对应审计问题**：P6、H1、H3、H4。

---

## 7. M7｜跨模块并行：文件所有权与集成责任

### 7.1 并行前置条件（全部满足才允许并行）

1. 契约已冻结（OpenAPI/字段/错误码），并写入 `implementation-plan.md`。
2. 每个文件只有一个写入者（ownership 表）。
3. 各轨道的测试输入/输出边界明确。
4. 指定集成责任人（默认 project-architect）与合并顺序。

### 7.2 所有权表模板

| 轨道 | 负责 Agent | 可写文件（glob） | 只读依赖 | 交付物 | 合并顺序 |
|------|-----------|----------------|---------|--------|---------|
| DB | database-engineer | `apps/api/alembic/**`、`modules/*/models.py` | 现有 schema | 迁移 + 回滚 | 1 |
| Backend | backend-engineer | `modules/*/service.py`、`repository.py`、`router.py`、`schemas.py` | 迁移 head | 端点 + OpenAPI | 2 |
| Frontend | frontend-engineer | `apps/*-web/src/**`、`apps/miniapp/src/**` | 冻结契约 | 页面 + 构建证据 | 3 |
| MCP | mcp-engineer | `apps/api/src/app/ai/**` | Service 能力 | Tool + 用例 | 与 2/3 并行（契约不变时） |

### 7.3 冲突处理

- 同文件二次写入 → 必须停下，由调度器仲裁，禁止覆盖。
- 契约变更 → 重新冻结 + 受影响轨道重跑对应验证。
- 集成失败 → 责任归于集成责任人（architect），不以"各轨道都 PASS"代替集成 PASS。

**对应审计问题**：P5、H3。

---

## 8. 问题—方案对照表（可追溯）

| 审计问题 | 对应方案 | 预期作用（待验证） |
|---------|---------|-------------------|
| P1 规则重复 | M3 + M4 | 降低常驻与重复阅读成本 |
| P2 产物脱钩 | M1 | L1/L2 不再产 9 份文档 |
| P3 验证不分级 | M5 | 低风险任务不再全量集成/浏览器验证 |
| P4 重复读取 | M3 + M6 | 记录已读区段，减少三次读同一代码 |
| P5 并行无所有权 | M7 | 安全并行；冲突可归责 |
| P6 无遥测 | M6 | 指标可测，优化可证伪 |
| P7 命名漂移 | M1 产物清单固定 + 任务记录校验 | 单一 Feature 目录 |

---

## 9. 效果验证实验设计

### 9.1 设计

- **样本**：后续 4 个任务，风险等级相同（建议 2 个 L3 + 2 个 L4，或同一 Feature 拆出的 4 个等价子任务）。
- **分组**：
  - 基线组：完全按现状 Rules/Skills 执行（2 个）。
  - 试点组：按 M1/M2/M3/M5/M6 执行（2 个）。
- **不变条件**：同一验收人、同一测试环境、同一代码库基线。

### 9.2 判定门槛（预注册，避免事后解释）

| 指标 | 期望方向 | 最低可接受 |
|------|---------|-----------|
| Lead Time | 下降 | 试点组中位数 < 基线组 |
| First-pass Acceptance | 不下降 | ≥ 基线 |
| Rework Rate | 下降 | ≤ 基线 |
| 安全/租户/权限类缺陷 | **必须为 0** | 任何 1 例即判定方案失败 |
| 产物完整性（L4） | 不下降 | 9 份齐全 |

### 9.3 报告

实验结束后新增 `docs/engineering/ai-coding-efficiency-experiment-1.md`，给出原始数据与结论；**未完成实验前不更新本方案中的任何"提升"表述**。

---

## 10. 分阶段落地建议（均需批准）

| 阶段 | 内容 | 风险 | 状态（批准后） |
|------|------|------|----------------------|
| **S0** | 只启用 M6 遥测（不改任何规则） | 低 | **已批准并落地（2026-10-21）** |
| **S1** | 启用 M1 分级 + M2 Agent 矩阵（引用型附录） | 中 | **已批准并落地（2026-10-24）**：`orchestration.md` 附录 A |
| **S2** | M3 上下文分层 + M4 去重映射 | 中 | **部分落地（2026-10-24）**：M3 → `orchestration.md` 附录 B；M4 暂缓 |
| **S3** | M5 测试分层表 | 中 | **已批准并落地（2026-10-24）**：`testing.md` 附录 |
| **S4** | M7 并行所有权模板 | 低 | **已批准并落地（2026-10-24）**：`feature-delivery-lifecycle/SKILL.md` 附录 A |

> 未经人工批准，上述文件**一个都不改**。

---

## 11. 决策记录（2026-10-21 人工批准）

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | L1–L4 四级 | **接受**，按本方案定义执行 |
| 2 | L3 及以下 "No DB change" 时是否调用 database-engineer | **可不调用**，由计划中记录 "No DB change（已核对）" |
| 3 | L1/L2 是否可用 `task-record.md` 替代 9 份产物 | **可用**，仍须保留 diff、测试日志与人工验收 |
| 4 | 遥测记录位置 | **`docs/engineering/task-records/`** |
| 5 | 实验样本 | **F6.3–F6.6**（前 2 个基线，后 2 个试点） |
| 6 | S0 先行试点 | **批准**，已落地遥测模板；未修改任何 Rules/Skills/CI |

### 决策记录（2026-10-22 人工批准，依据 `ai-coding-efficiency-experiment-1.md` §6）

| # | 决策点 | 结论 |
|---|--------|------|
| 7 | 分组偏差处置 | 决策 5 的试点组（F6.5/F6.6）实际按基线执行，**补做试点**：F6.7/F6.8 为试点样本，执行口径见实验报告 §7 |
| 8 | S1–S4 | **暂缓**，待 F6.7/F6.8 试点 A/B 结果后逐项审批 |
| 9 | 遥测模板修订 | **批准**：`TEMPLATE.md` 新增子 Agent 回传要求（工具调用数/读取行数/阶段边界）与第 9 节试点执行声明；仅改模板，不改 Rules/Skills |
| 10 | F6.3 R1 工具可靠性 | 登记为独立改进项，暂不立项 |

> 后续 S1–S4 仍属"提案"，未获批准，不得实施。

### 决策记录（2026-10-24 人工批准，依据 `ai-coding-efficiency-experiment-1.md` §8–§11 试点 A/B）

| # | 决策点 | 结论 |
|---|--------|------|
| 11 | S1（M1 分级 + M2 Agent 矩阵） | **批准**：以引用型附录写入 `.trae/rules/agent/orchestration.md`（附录 A），不改正文 |
| 12 | S2（M3 分层读取 + M4 去重映射） | **部分批准**：M3 写入 `orchestration.md`（附录 B）；**M4 暂缓**（试点未触发冲突，无正反证据） |
| 13 | S3（M5 测试分层表） | **批准**：以引用型附录写入 `.trae/rules/testing/testing.md`；并发专项为不可裁剪保留项 |
| 14 | S4（M7 并行所有权） | **暂缓**：M7 未在试点启用、无数据；待下 1–2 个跨模块任务启用 M7 后再审批 |

> 写入形式均为**引用型附录**（标注批准日期与来源文档），可独立回滚，不改现有规则正文。

### 决策记录（2026-10-24 人工批准 S4）

| # | 决策点 | 结论 |
|---|--------|------|
| 15 | S4（M7 并行所有权模板） | **批准**（基于设计推理，无试点数据）：以引用型附录写入 `feature-delivery-lifecycle/SKILL.md`（附录 A）；首次启用时须记录并行/串行耗时对比与冲突情况作为补充证据 |

---

## 12. 停止条件

- 本方案到此为止：不修改任何 Rules/Skills/业务代码/CI。
- 等待人工审核并逐项批准后，才进入实施；实施本身仍按 `feature-delivery-lifecycle` 与 `.trae/rules/` 执行。
- 不自动开始重构，不顺便实现 F6.0 / F7.0 业务功能。
