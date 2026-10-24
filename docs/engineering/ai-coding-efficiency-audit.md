# AI Coding 开发效率审计报告

> 审计日期：2026-10-21
> 审计性质：**只读审计**（未修改任何 Rules / Skills / Agent 定义 / 业务代码 / CI 配置）
> 审计对象：`.trae/rules/`、`.trae/skills/`、`docs/ai/` 协作协议、`docs/delivery/` 交付基线、`docs/features/` 产物、CI 与测试脚本
> 配套文档：`docs/engineering/ai-coding-optimization-plan.md`（优化方案，同样只提方案不实施）

---

## 0. 证据等级约定

本报告严格区分事实与推测，避免把假设写成结论。

| 等级 | 定义 | 本报告用法 |
|------|------|-----------|
| **E1 已核实** | 直接读取文件/执行命令得到的可复现事实（含 `文件:行号` 或命令输出） | 作为"已确认问题" |
| **E2 会话观察** | 本次多轮会话中直接观察到的行为（重复读取、重复同步文档），可回溯对话但无独立日志 | 标注为"观察证据" |
| **E3 UNKNOWN** | 缺少日志/计时数据，无法证实的推测 | 只列入"待验证假设"，不作结论 |

**关键限制**：仓库内**没有**任何 AI 任务耗时日志、Agent 调用日志或 CI 耗时记录；`git log` 最后一条提交为 `2026-09-19`（共 69 次提交），此后包括 F3.1～F7.0 在内的全部工作均处于未提交状态。因此"模型响应等待 / 工具执行 / 规划 / 返工"的分钟级拆解**无法测量**，统一标记 UNKNOWN。

---

## 1. 现有工作流图

### 1.1 分层结构（现状）

```
┌──────────────────────────────────────────────────────────────────────┐
│ 常驻上下文（alwaysApply: true，9/15 条 Rule，约 483 行）               │
│ orchestration.md(236) · architecture(114) · security(70) · ai(63)     │
│   └─ 规定：复杂任务必须先读 v3 协作协议                               │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ 触发
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 协作协议层 docs/ai/workflows/multi-agent-collaboration-v3.md (461 行) │
│ Phase 0 侦察 → Phase 1 Architect 分析+契约冻结 → Phase 2 四轨并行      │
│ → Phase 3 Reconciliation → Phase 4 计划 → Phase 5 实施                 │
│ → Phase 6 测试 → Phase 7 四方 Review → Phase 8 报告                   │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ 引用
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 交付流水线 .trae/skills/orchestration/feature-delivery-lifecycle       │
│ Stage 0 BACKLOG → 1 READY → 2 REQUIREMENT → 3 USER FLOW → 4 ACCEPTANCE │
│ → 5 DESIGN → 6 ARCHITECTURE → 7 DEVELOPMENT → 8 STATIC → 9 TESTING    │
│ → 10 REVIEW → 11 ACCEPTANCE → 12 CLOSE                                │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ 产物
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 每个 Feature 固定 9 份产物（requirement / user-flow / acceptance /      │
│ implementation-plan / implementation-report / static-verification /    │
│ runtime-test-report / review / release-note）                          │
│ + 专项 Skill：minimal-change-guard、miniapp-runtime-smoke-test          │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 三套并存的阶段编号（已核实）

| 来源 | 阶段划分 | 证据 |
|------|---------|------|
| `orchestration.md` | 7 步：Analyze → Architect → Specialist → Reconcile → Implement → Test → Review | [orchestration.md#L52-L58](file:///Users/lixiang/Desktop/class_booking_system/.trae/rules/agent/orchestration.md) |
| `multi-agent-collaboration-v3.md` | Phase 0–8（9 段） | [v3#L267-L329](file:///Users/lixiang/Desktop/class_booking_system/docs/ai/workflows/multi-agent-collaboration-v3.md#L267-L329) |
| `feature-delivery-lifecycle/SKILL.md` | Stage 0–12（13 段） | [SKILL.md#L41-L98](file:///Users/lixiang/Desktop/class_booking_system/.trae/skills/orchestration/feature-delivery-lifecycle/SKILL.md#L41-L98) |

同一生命周期存在三种编号，Agent 每次需要自行做映射；这是后续"漏环节"与"重复执行"的结构性来源。

### 1.3 两套并存的产物体系

| 体系 | 目录 | 证据 |
|------|------|------|
| 生命周期产物 | `docs/features/<ID>/` 9 份 | 23 个 Feature 目录，`release-note.md` 共 23 份 |
| 协作协议产物 | `docs/ai/architecture/*`、`docs/ai/implementation/*`、`docs/ai/tests/*` | [v3#L360-L379](file:///Users/lixiang/Desktop/class_booking_system/docs/ai/workflows/multi-agent-collaboration-v3.md#L360-L379) |

F3.1～F5.4 走的是前者，`ai-course-query` 走的是后者，二者没有互相引用规则。

---

## 2. 典型任务调用链（现状逐步拆解）

以"修改一个已有模块的业务规则"为例（E1 证据来自规则/Skill 文本）：

| # | 步骤 | 输入/动作 | 产出 | 重复或浪费点 |
|---|------|----------|------|-------------|
| 1 | 读取常驻规则 | 10 条 alwaysApply 规则（约 480 行） | 约束集合 | 每次请求固定上下文成本 |
| 2 | 判定"复杂任务" | orchestration.md 要求读 v3 | 强制读取 461 行 v3 | 与 Stage 1 READY 判定重复 |
| 3 | READY 判定 | 读 Backlog + DoR + 真实代码 | 选型结论 | 与 v3 Phase 0 侦察重复同一批代码 |
| 4 | REQUIREMENT / FLOW / ACCEPTANCE | 写 3 份文档 | 3 份 md | 此时尚未做 spec-vs-code 对账（Stage 5 才做）→ 返工风险 |
| 5 | DESIGN / ARCHITECTURE | 读真实代码对账 | implementation-plan | 与步骤 3/4 第三次读同一批代码 |
| 6 | DEVELOPMENT | 改代码 | implementation-report | 一次写入 |
| 7 | STATIC | minimal-change-guard：5 条 git 命令 + 逐文件编译 | static-verification | 与 Stage 7 的"每文件 py_compile"重复 |
| 8 | TESTING | 按 testing.md 跑 unit/integration/并发 | runtime-test-report | 风险无关的全量执行（无分级） |
| 9 | REVIEW | 主 Agent 或 architect 复核 AC | review | 与 Stage 8/9 的验证项部分重叠 |
| 10 | ACCEPTANCE | 人工验收 | 用户确认 | 必要保留 |
| 11 | CLOSE | 更新 backlog/roadmap + release-note | 2 处状态 + 1 份文档 | 必要，但同内容第三次陈述 |

---

## 3. 已确认问题（E1）

### P1｜常驻规则与协议重复，上下文成本固定偏高（优先级 P0）

**现象**
- `.trae/rules/` 共 15 个文件、681 行；其中 **9 个 `alwaysApply: true`**，合计约 483 行常驻。证据：逐文件 frontmatter 扫描（`orchestration.md` 236 行；architecture 3 条约 114 行；security 3 条约 70 行；ai 2 条约 63 行）。
- `orchestration.md` 的 Agent Selection / Handoff / Reconciliation / Verification 与 v3 §2、§6、§11 及 lifecycle SKILL 的 Stage 7–10 语义重复。证据：[orchestration.md](file:///Users/lixiang/Desktop/class_booking_system/.trae/rules/agent/orchestration.md) 第 2–11 节 vs [v3#L57-L73](file:///Users/lixiang/Desktop/class_booking_system/docs/ai/workflows/multi-agent-collaboration-v3.md#L57-L73)、[v3#L187-L243](file:///Users/lixiang/Desktop/class_booking_system/docs/ai/workflows/multi-agent-collaboration-v3.md#L187-L243)。
- 测试约束同时存在于 `testing.md`（32 行）、lifecycle Stage 9、v3 Phase 6、miniapp Skill 四处。

**影响**
- 每个任务都要为重复内容支付上下文与对齐成本；三套阶段编号导致 Agent 需要额外推理"现在处于哪一步"，易漏环节或重复执行。
- **预计**（未实测）这是固定开销，任务越碎（如单文件修复）相对浪费越大。

### P2｜产物数量与任务规模脱钩（优先级 P0）

**现象**
- 23 个 Feature 目录均按 9 份产物交付，共 **233 个 md 文件、22,553 行**（另有 1 个重复目录，见 P7）。证据：`find docs/features -name "*.md" | wc -l` = 233；`cat | wc -l` = 22,553。
- 其中 F3.1 的真实代码改动为 **3 个 import 符号**，却产出 9 份文档 + 17 条运行时用例 + 6 项 UNKNOWN，review 明确写"无需任何代码返工"。证据：[review.md#L100](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.1-miniapp-crash-fix/review.md#L100)；改动量见 [static-verification.md#L112](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.1-miniapp-crash-fix/static-verification.md#L112)。
- 原型类工作的文档体量：F6.0 **3,339 行 / 318KB**；F7.0 **1,313 行 / 113KB**。证据：`wc -lc` 输出。
- **会话观察（E2）**：F7.0 多轮微调中，每次 UI 小改动都要同步 README、test-report、interaction-spec、solution-design、screen-inventory、prototype-acceptance、open-decisions、entity-state-model 等 8–10 份文档；文档同步成为单次改动的主要工作量。

**影响**
- 固定产物清单对 L1/L2 任务产生纯开销；文档漂移又反向制造"文档与代码不一致"的返工。

### P3｜验证强度与风险无关，测试分层缺失（优先级 P0）

**现象**
- `testing.md` 要求业务逻辑改动跑"真实 Uvicorn + 真实 PG + 真实 Redis、不 mock"的集成测试（[testing.md#L16-L20](file:///Users/lixiang/Desktop/class_booking_system/.trae/rules/testing/testing.md#L16-L20)），但 CI 只执行 `uv run pytest tests/unit`（[ci.yml#L63-L64](file:///Users/lixiang/Desktop/class_booking_system/.github/workflows/ci.yml#L63-L64)）。
- miniapp 任何页面改动都要求 Docker → API → H5 → token 注入 → 浏览器逐页验证（[miniapp SKILL#L12-L20](file:///Users/lixiang/Desktop/class_booking_system/.trae/skills/testing/miniapp-runtime-smoke-test/SKILL.md#L12-L20)），F3.1 的 3 行 import 修复同样走了全链路。
- `skill-registry.md` 明确登记"测试层级决策树"仍为 **Planned**（[skill-registry.md#L33](file:///Users/lixiang/Desktop/class_booking_system/docs/ai/skill-registry.md#L33)）。
- 对照：轻量校验其实很便宜——F7.0 原型 106 条断言实测 **0.14s**（`/usr/bin/time -p node verify-prototype.js`）。瓶颈不在脚本，而在"全量人工/浏览器验证 + 全量文档同步"。

**影响**
- 低风险改动承担高风险验证成本；高风险改动又因 CI 覆盖不足而依赖人工重跑。

### P4｜跨阶段重复读取与"先写文档后对账"（优先级 P1）

**现象**
- v3 Phase 0（侦察）→ Phase 1（Architect 冒烟+契约存在性）→ Phase 2（Specialist `[VERIFY]`）对同一批代码/端点重复核验。
- v3 固化规则 R4 要求 Database Agent 即使"No Change"也必须完成四项检查并给出**至少 1 个 `[NEW]`**（[v3#L406](file:///Users/lixiang/Desktop/class_booking_system/docs/ai/workflows/multi-agent-collaboration-v3.md#L406)），属于强制产出。
- lifecycle 在 Stage 2–4 先写 requirement/flow/acceptance，Stage 5 才做 spec-vs-code 对账；F3.1 因此在对账阶段记录了 2 处文档失真并需修正措辞（[review.md#L104](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.1-miniapp-crash-fix/review.md#L104)、[implementation-plan.md](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.1-miniapp-crash-fix/implementation-plan.md) 的 Conflict 节）。

**影响**
- 同一事实被读取 3 次；文档先于事实产出，必然产生返工。

### P5｜并行缺少文件所有权与集成责任约定（优先级 P1）

**现象**
- lifecycle Stage 7–10 严格串行；v3 Phase 4 固定顺序 DB → Backend → OpenAPI → gen:types → Frontend，仅"MCP 重构不改契约时"可与前端并行（[v3#L306-L315](file:///Users/lixiang/Desktop/class_booking_system/docs/ai/workflows/multi-agent-collaboration-v3.md#L306-L315)）。
- `orchestration.md` 仅要求"不要让多个 Agent 无序修改同一文件"，但**没有**文件所有权表、合并顺序、集成责任人的产物规范（全文无 ownership/owner 相关条款）。

**影响**
- 本可并行的独立文件改动被迫串行；若真并行则冲突风险不可控。

### P6｜缺少任务遥测，优化无法度量（优先级 P0，元问题）

**现象**
- 所有 Feature 产物均无"开始/结束时间、工具耗时、Agent 交接次数、返工次数"字段（对 233 个 md 做 `耗时/elapsed/duration` 检索，命中仅来自需求描述或 v3 文本，无结构化计时字段）。
- CI 无耗时上报；`git log` 停留在 2026-09-19，AI 协作期的工作全部未提交，无法用提交时间/diff 粒度还原过程。
- release-note 的 PASS 结论引用的是同一 Feature 内 Agent 自产报告（如 F3.1 release-note 引用 runtime-test-report），**无独立复跑证据链**。

**影响**
- 任何优化都无法证明有效；也无法定位耗时大头（模型等待 / 工具 / 规划 / 返工）。

### P7｜产物命名漂移已发生（优先级 P2）

**现象**
- 同一 Feature 编号存在两个目录：`F3.4-list-four-states/`（仅 1 份 implementation-plan.md）与 `F3.4-list-page-states/`（9 份产物）。证据：`ls` 输出。
- 与项目记忆中的历史教训一致（"产物命名漂移"）。

**影响**
- 检索与验收时出现双源，增加人工判定成本。

---

## 4. 待验证假设（E3 / UNKNOWN）

| # | 假设 | 为何未确认 | 验证方式 |
|---|------|-----------|---------|
| H1 | 模型响应等待是端到端耗时最大头 | 无 AI 侧计时日志 | 在任务记录中加入每轮开始/结束时间戳（见 M6） |
| H2 | Architect 在简单任务上被过度调用 | 规则允许直接处理，且本会话原型任务未调用；样本不足 | 统计 M2 落地前后 Agent 调用次数与任务等级 |
| H3 | 并行化能显著缩短跨模块任务 | 无并行执行记录 | 选 1 个跨模块 Feature 做并行试点并记录墙钟时间 |
| H4 | 文档同步是微调类任务的主要耗时 | 仅有会话观察（E2），无计时 | 在 M6 中单独记录"文档同步"工具轮次与时长 |

> 以上一律不得在优化方案中写成"已证明"。

---

## 5. 耗时结构（可测部分与 UNKNOWN）

| 环节 | 现状证据 | 结论 |
|------|---------|------|
| 工具执行（轻量脚本） | F7.0 verify 106 断言 **0.14s** | 非瓶颈 |
| 文档产出 | 23 Feature × 9 份 = 22,553 行；F6.0 318KB、F7.0 113KB | 体量大，**预计**为主要成本之一（未计时） |
| 测试执行 | CI 仅 unit；集成/并发需本地起真实服务 | 成本存在，未计时 |
| 模型响应等待 | 无日志 | UNKNOWN |
| 任务规划/对齐 | 三套阶段编号 + 两套产物体系 | 结构性成本，未计时 |
| 返工 | F3.1 文档失真 2 处；F7.0 多轮需求反转（默认封面图→回退占位、图标替换→删除） | 已发生，次数可数、时长 UNKNOWN |

---

## 6. 优化优先级矩阵

| 优先级 | 问题 | 理由 |
|--------|------|------|
| **P0** | P1 规则重复 / P2 产物与规模脱钩 / P3 验证不分级 / P6 无遥测 | 影响每个任务，且 P6 不解决则无法验证其它优化 |
| **P1** | P4 重复读取与先写后对账 / P5 并行无所有权 | 影响 L3/L4 与跨模块任务 |
| **P2** | P7 命名漂移 | 局部治理问题 |

---

## 7. 优化前后流程对比（目标形态，未实施）

| 环节 | 现状 | 目标（详见优化方案） |
|------|------|---------------------|
| 任务入口 | 一律先读 v3 + 走 12 阶段 | 先做 **L1–L4 分级**，按级选流程 |
| Rules | 10 条常驻、内容重复 | 常驻仅保留不变量索引；流程性内容单一来源 |
| 文档 | 固定 9 份 | L1/L2 用 1 份任务记录；L3/L4 保留完整产物 |
| 测试 | 业务改动默认真实服务集成 | 按风险分层：编译/定向单测/集成/并发/人工 |
| 并行 | 串行，无所有权 | 文件所有权表 + 契约冻结 + 集成责任人 |
| 度量 | 无 | 任务记录 + 指标看板（JSONL） |
| 验收 | Agent 自证 | 保留 diff/日志/运行时证据 + 人工验收，禁止自证通过 |

---

## 8. 优化可能引入的风险

| 风险 | 说明 | 缓解 |
|------|------|------|
| 分级误判 | 把安全/租户/迁移类任务误判为 L1/L2 → 验证不足 | 硬性升级触发器：认证、授权、租户、迁移、支付、AI 写操作一律 ≥L4 |
| 上下文裁剪过度 | 漏读约束导致违规 | 分级只决定"流程文档"，架构/安全 Rule 仍按 glob 强制加载 |
| 并行冲突 | 多 Agent 同文件/同契约改动 | 文件所有权表 + 契约先冻结 + 单集成责任人 |
| 文档删减导致追溯缺失 | 审计链断裂 | L1/L2 保留任务记录 + diff + 测试日志；L3/L4 产物不减 |
| 遥测变成新负担 | 记录本身耗时 | 字段固定、尽量自动采集、单文件追加 |

---

## 9. 验证优化效果的指标与实验方案（摘要）

完整方案见 `ai-coding-optimization-plan.md` 第 9 节。核心指标：

1. **端到端交付时长**（任务开始 → 人工验收通过）
2. **返工率**（REVIEW 判 NEEDS_FIX 或需求反转次数 / 任务数）
3. **产物当量**（每任务 md 行数 / 变更代码行数）
4. **验证时长**（各层测试实际耗时）
5. **首次验收通过率**
6. **Agent 调用次数与空转次数**（无产出或职责外的调用）

实验设计：选取后续 4 个同等级 Feature，前 2 个按现状执行（基线），后 2 个按分级方案执行；同一批指标、同一验收人。**在拿到实测数据前，本报告不声称任何提升幅度。**

---

## 10. 结论

已确认的结构性问题集中在四点：**规则/协议重复（P1）**、**产物与规模脱钩（P2）**、**验证不分级（P3）**、**无遥测（P6）**。这四项都会随任务数量线性放大，且相互强化：无遥测 → 无法证明分级是否安全 → 只能继续全量执行 → 成本继续上升。

本阶段只完成审计，**不修改任何现有 Rules / Skills / 业务代码 / CI 配置**，等待人工审核后再决定是否实施优化方案。
