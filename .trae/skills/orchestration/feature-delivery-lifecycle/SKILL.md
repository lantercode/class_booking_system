---
name: feature-delivery-lifecycle
description: 驱动已排期 Feature 从 Backlog 选型到 Close 的门控交付流水线，产出标准 Feature 文档与验收记录。当需要选型、立项、设计、实施、静态/运行时验证、Review、人工验收或关闭一个 Feature 时使用。不用于一次性问答或零散小修。
---

# Feature Delivery Lifecycle

将一个已进入 `docs/delivery/feature-backlog.md` 的 Feature，按门控流水线推进到关闭。本 Skill 是**产物驱动的执行程序**；协作关系遵循 `docs/ai/workflows/multi-agent-collaboration-v3.md`（引用，不复制），项目约束遵循 `.trae/rules/`（引用，不复制）。

首个完整样板：`docs/features/F3.1-miniapp-crash-fix/`（9 份产物，可直接对照）。

## When to Use

- 用户要求从 Backlog 选"下一项开发 Feature"、为某 Feature 立项、出实施方案、实施、验证、Review 或 Closing
- P0/P1 修复批次需要统一的交付留痕

**Do Not Use**：纯咨询/问答、无需留痕的零散小修（直接使用 minimal-change-guard 即可）、重新做 Candidate Audit。

## Inputs

| 输入 | 来源 |
|------|------|
| Backlog 条目（ID、Goal、Scope、Dependencies、Tasks、Required Agents） | `docs/delivery/feature-backlog.md` |
| 优先级与路线位置 | `docs/delivery/product-gap-analysis.md`、`docs/delivery/release-roadmap.md` |
| 门控标准 | `docs/delivery/delivery-criteria.md`（DoR / DoD） |
| 项目强制约束 | `.trae/rules/`（只读引用） |

## Feature 类型 → 执行形态（不得无条件调全部 Agent）

| 类型 | project-architect | 执行 Agent | DESIGN/ARCHITECTURE 环节 |
|------|-------------------|-----------|--------------------------|
| Bug Fix（根因明确、单域、≤少量文件） | 不需要 | 对应域 Agent（或主 Agent 直接做） | 可合并为轻量 implementation-plan，仍需核验真实代码 |
| UI Feature | 简单单页不需要；跨端/跨模块需要 | frontend-engineer | 需要（含 API 契约核对） |
| Backend Feature | 跨模块需要 | backend-engineer | 单模块可轻量；涉及事务/权限必须完整 |
| Database Feature | 跨模块需要；纯迁移可不走 | database-engineer | 必须（迁移、回填、锁、回滚） |
| MCP/AI Feature | 需要 | mcp-engineer（Service 能力缺口时 backend-engineer 先补） | 必须（四关校验、Tool→Service、契约） |
| Cross-domain Feature | **必须** | architect 拆分后按域调用，不默认全员 | 必须 |

判断不了类型或跨域边界时，默认走 architect，但这是例外不是惯例。

## Process（阶段与门控）

### 0. BACKLOG
读取 Backlog 条目与依赖；确认前置 Feature 状态。依赖未满足 → Blocked Handling。

### 1. READY（选型判定）
- 按 P0/P1、业务依赖、完成条件、现有实现判断
- 核查开发前置条件是否真实存在（读代码验证，禁止凭假设）
- 输出选型结论，格式：Selected Feature / Why / Dependencies / Existing Capabilities / Missing Capabilities / Risks / Required Agents / Definition of Ready
- 门控判定：**READY 或 NOT READY**；NOT READY 必须列出缺失项并停止

### 2. REQUIREMENT
创建 `docs/features/<FEATURE-ID>-<name>/requirement.md`：Goal、Problem（带文件:行号证据）、User Story、Scope、Out of Scope、User Roles、Business Rules、Dependencies、Risks。
**门控**：Scope 与 Out of Scope 必须同样具体。

### 3. USER FLOW
同目录 `user-flow.md`：主流程 + 异常流程 + 空状态 + Loading + Error + Success + Permission/Authentication。**禁止只写 Happy Path。**

### 4. ACCEPTANCE
`acceptance.md`：每条 AC 必须可判定 PASS/FAIL，编号分组（静态/构建/运行时/权限/健壮性），给出验证方式。

### 5. DESIGN（按类型决定深度）
- 实施前必须与**当前真实代码**对账（spec-vs-code 对账，见下）
- 轻量 Bug Fix：implementation-plan 可精简但必须含 Root Cause、Exact Fix、Verification
- 复杂/跨域/Database/MCP：调用 project-architect 产出完整 `implementation-plan.md`
- **对账冲突**：发现文档与真实代码不一致时，以真实代码为准，记录 `## Conflict`（Conflict / Evidence / Impact / Recommendation），并同步修正受影响文档的验收口径

### 6. ARCHITECTURE（门控，仅适用时）
跨域、数据库结构、MCP/AI、契约变更必须经 architect；确认分层、租户、事务、契约兼容性（见 `.trae/rules/architecture/`）。不适用时显式记录"跳过及原因"。

### 7. DEVELOPMENT
- 开工前先跑 minimal-change-guard 的"修改前"检查（git status、识别预存改动、冻结 expected files 白名单）
- 按 Scope 实施；同一文件修改合并；Python 文件每改完一个即 `python3 -m py_compile`
- Handoff 遵循 v3 协议（Analysis / Decision / Changed Files / Dependencies / Risks / UNKNOWN / Handoff）
- 完成后写 `implementation-report.md`：Changed Files、Exact Changes、Scope Verification、Tests Run、Results、Risks、UNKNOWN、Handoff

### 8. STATIC VERIFICATION
执行 minimal-change-guard（其脚本与判定见该 Skill）；产出 `static-verification.md`，逐条映射 AC 的静态/构建类条款，给出 PASS/FAIL/BLOCKED。

### 9. TESTING（运行时）
- miniapp 改动 → 调用 miniapp-runtime-smoke-test
- 后端改动 → 按 `.trae/rules/testing/testing.md` 跑 pytest 对应层级（unit/integration/并发回归）
- 产出测试报告，结果词表：PASS / FAIL / BLOCKED / UNKNOWN / NOT TESTED（不允许"基本通过"）

### 10. REVIEW
- 简单单域：主 Agent 对照 AC 复核
- 复杂/跨域/P0：调用 project-architect 做最终 Feature Review，产出 `review.md`（Scope / Architecture / Code / Regression / Acceptance / Risks / UNKNOWN / Recommendation）
- 结论只能是 **READY_FOR_ACCEPTANCE** 或 **NEEDS_FIX**；NEEDS_FIX 回到阶段 7

### 11. ACCEPTANCE
需要人工环境（微信开发者工具、真实数据等）的条款交用户人工验收；用户确认通过前不得 Close。

### 12. CLOSE
- Backlog 该 Feature 加 `Status：✅ DONE（日期，人工验收通过）` 与交付物清单
- Roadmap 对应行加 ✅ DONE
- 实施中发现的新技术债追加到 Backlog 附录（编号 D-<Feature>-n），不顺手修
- 写 `release-note.md`：Feature / Problem / Fix / Files Changed / Tests / Acceptance / Known Risks / Release Notes
- 不删除任何测试结果，不改写历史记录

## Decision Gates 汇总

| Gate | 通过条件 | 不通过动作 |
|------|---------|-----------|
| READY | DoR 全满足且前置条件经代码验证 | 列缺失项，停止 |
| REQUIREMENT/FLOW/ACCEPTANCE | 三件套齐备、AC 可判定 | 补齐后继续 |
| DESIGN | 与真实代码对账无未决 Conflict | 记录冲突并修正 |
| ARCHITECTURE | 分层/租户/事务/契约无违规（或显式跳过） | 回设计 |
| STATIC | actual files ⊆ expected scope 且构建/类型通过 | NEEDS_FIX，不改代码先报告 |
| TESTING | 0 FAIL；BLOCKED/UNKNOWN 有明确替代验证路径 | FAIL 回开发；环境阻塞走 Blocked Handling |
| REVIEW | READY_FOR_ACCEPTANCE | NEEDS_FIX 回开发 |
| ACCEPTANCE | 用户人工确认 | 等待 |

## Required Artifacts（Feature 目录）

```
docs/features/<FEATURE-ID>-<name>/
├── requirement.md            # 阶段2
├── user-flow.md              # 阶段3
├── acceptance.md             # 阶段4
├── implementation-plan.md    # 阶段5（轻量 Bug 可精简，不可缺）
├── implementation-report.md  # 阶段7
├── static-verification.md    # 阶段8
├── <runtime>-test-report.md  # 阶段9
├── review.md                 # 阶段10（P0/复杂必须；简单可并入 report）
└── release-note.md           # 阶段12
```

## Stop Conditions

- READY 门控 NOT READY
- 任何门控 FAIL 且用户未授权调整 Scope
- 发现需要扩大 Scope 才能继续 → 停止并回到 REQUIREMENT 走变更，禁止顺手扩
- 用户要求暂停

## Blocked Handling

记录：阻塞项 / 当前已检查到的事实 / 解除条件 / 建议下一步。环境阻塞（服务未起、账号缺失、原生工具不可用）用 BLOCKED 或 UNKNOWN 标注并给替代验证路径，禁止用"基本通过"掩盖。

## 边界

- 不复制 `.trae/rules/` 约束正文，只引用
- 不复制 v3 协作协议，只规定本流水线在何处交接
- 不重排优先级、不新增/删减 Backlog Feature（技术债登记除外）
- 不为凑产物创建无信息量文档；简单 Bug Fix 的 plan/review 可精简但门控不可跳

---

## 附录 A：跨模块并行所有权（M7，2026-10-24 批准）

> 引用型补充模板。完整定义与审批依据见 `docs/engineering/ai-coding-optimization-plan.md` §7 与 `docs/engineering/ai-coding-efficiency-experiment-1.md` §10/§11。本附录不替代上文各阶段门控，仅在阶段 6（Implement）增加并行委派选项。

### 启用条件（全部满足才可并行）

1. 任务拆分为 **≥2 个子任务**，且各子任务改动的**文件集合互不相交**（无共享文件）。
2. 子任务之间无运行时依赖（如：后端端点契约已冻结，前端不依赖后端未提交的实现）。
3. 契约（API DTO、响应结构、状态枚举）已在阶段 2–4 冻结，子 Agent 无需再协商。

### 并行所有权模板

| 角色 | 职责 | 禁止 |
|------|------|------|
| 主 Agent | 拆分任务、声明并行边界、冻结契约、汇总子 Agent 结果、跑集成验证 | 不替子 Agent 实现 |
| 子 Agent A（如 backend） | 仅改自己白名单内文件、自验、回传 Handoff | 不触碰 B 的文件 |
| 子 Agent B（如 frontend） | 同上 | 不触碰 A 的文件 |

### 集成阶段（主 Agent）

- 并行完成后，主 Agent 必须执行**全量集成验证**：相关测试 + 双端构建 + 受影响功能冒烟。
- 若集成失败，定位到具体子任务后回滚该子任务或修复，不静默通过。

### 遥测要求

- 任务记录须注明：并行了哪几个子任务、各自文件白名单、集成验证是否通过、是否出现冲突。
- 首次启用 M7 的任务须额外记录并行耗时 vs 预估串行耗时，作为补充证据。

### 不适用场景

- 子任务共享同一文件 → 必须串行。
- 契约未冻结 → 必须串行（先冻结契约）。
- 涉及同一数据库表的并发写 → 串行并遵循统一锁顺序。

