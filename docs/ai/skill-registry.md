# Skill Registry — class_booking_system

> Skill Candidate Audit
> 审计日期：2026-09-26
> 审计范围：基于 docs/delivery 5 份基线文档、F3.1 完整交付实践、`.trae/rules/`（14 条）、5 个 Agent、AI/MCP/Testing 现状
> 原则：**本文件只做候选识别与分级，不创建任何 Skill。**

---

## 分级定义

| 级别 | 含义 |
|------|------|
| **A. Stable** | 已有真实 Feature / 真实修复全程验证，流程、输入、输出稳定，可立即封装 |
| **B. Pilot** | 已真实出现过 1 次，但还需 1~2 次验证才能固化 |
| **C. Planned** | 按 Roadmap 未来必然重复，但尚未实践 |
| **D. Do Not Create** | 重复价值不足，普通 Prompt / Rule / Agent 已足够 |

---

## 候选清单

| Skill | Type | Evidence | Reuse Scenario | Dependencies | Status |
|---|---|---|---|---|---|
| **S1 feature-delivery-lifecycle**（Feature 门控交付全流程） | A | F3.1 全程执行：选型判定（READY/NOT READY）→ requirement/user-flow/acceptance → architect implementation-plan → 实施报告 → 静态验证 → 运行时验证 → review → closing（backlog/roadmap 状态 + release-note），9 份产物齐备且通过人工验收 | Backlog 中 F1.1~F7.3 每一个 Feature 的启动到关闭；P0/P1 修复批次 | delivery-criteria.md（DoR/DoD）、multi-agent-collaboration-v3.md、docs/features/F3.1/ 全套模板 | Stable |
| **S2 miniapp-runtime-smoke-test**（小程序运行时冒烟） | A | F3.1 实跑：Docker PG/Redis 拉起 → API 启动 → H5 dev server → API 注册/登录取 token → 注入 localStorage → browser_use 逐页验证 ReferenceError/控制台/拦截 → 输出 PASS/FAIL/BLOCKED/UNKNOWN 报告；17 PASS/0 FAIL/6 UNKNOWN | F3.2（类型清零回归）、F3.4（四态）、后续所有 miniapp Feature 与小程序端缺陷修复 | 测试租户/账号、H5 端口约定、runtime-test-report 模板；无需 MCP | Stable |
| **S3 minimal-change-guard**（最小改动守卫：diff 白名单 + 逐文件验证） | A | F3.1：改前 git status 防覆盖、diff --name-only/--stat/--check/numstat、预期改动白名单、AC-1 逐条核对；另据项目记忆，membership 审计修复（v1.1）确立"每改一个 Python 文件后 py_compile 验证、改前完整读文件"模式并已跨会话重复 | 任何外科手术式修复（P0 hotfix、审计整改、单文件 bugfix）；与语言无关的改动范围守卫 | git、py_compile（Python）/vue-tsc+build（前端）、static-verification 模板 | Stable |
| **S4 parallel-domain-audit**（多 Agent 并行领域审计 → 交付文档综合） | B | 基线审计实做 1 次：5 专业 Agent 并行只读审计 → project-baseline / gap-analysis / backlog / roadmap / delivery-criteria 5 份文档；流程跑通但仅此 1 次，综合去重/P0 校准手法未经第二次验证 | Phase 准出复评、Epic 级再审计、上线前全面体检 | 5 Agent、证据带文件:行号的审计输出格式；无需 MCP | Pilot |
| **S5 spec-vs-code-reconciliation**（需求文档与真实代码对账） | B | F3.1 architect 发现 2 处文档失真（570 行 try 作用域、"加载即崩"实为 try/catch 内静默失效），按 Conflict/Evidence/Impact/Recommendation 记录并修正验收口径；v3 协议也定义了 Reconciliation 但作为流程首次被真实使用 | 任何涉及既有代码描述的 Feature 立项、历史文档纠偏、接手他人方案 | architect 主导、只读代码调查；产物为 plan 内 Conflict 节 | Pilot |
| **S6 mcp-tool-onboarding**（新增 MCP Tool 端到端上线） | B | ai-course-query Phase 0-8 实做过查询类 Tool（intent 重排、tool 注册、runtime 注入），且有 mcp-test-v1→v1.1 两轮迭代与 test_mcp_server.py / test_multi_turn_booking.py；但写操作 Tool（create_booking/cancel）的幂等+确认链路尚未在运行时验证 | F5.1（AI 多轮预约）及未来所有新 Tool | `.trae/rules/ai/mcp.md`（四关校验）、Service 先行原则、pytest；FastMCP stdio 无外部 MCP 依赖 | Pilot |
| **S7 rbac-permission-matrix**（端点权限矩阵盘点） | C | F1.1 的明确前置缺口：翻转 PERMISSION_CHECK_BYPASS 前必须逐端点产出"资源:动作"矩阵（baseline/gap-analysis 已识别绝大多数端点裸奔）；尚无实践 | F1.1 启动、每次新增受保护端点时增量更新 | OpenAPI Schema 枚举端点脚本（resources 待建）、authorization.md；无需 MCP | Planned |
| **S8 alembic-migration-authoring**（数据库迁移编写与校验） | C | 现状 27 个迁移含 3 个 merge head、命名不统一（project_rules 附录债务）；F4.x（外键修复 bookings.membership_card_id）必然需要数据存在性核查 + 回填 + 约束迁移，尚未在近期会话实践 | F4.1 外键修复、所有 schema 变更、定时任务相关索引变更 | postgresql.md/transaction.md、多租户回填检查清单；无需 MCP | Planned |
| **S9 backend-change-verification**（后端改动验证套件） | C（趋向 B） | 项目记忆显示 booking 事务修复、membership 6 步整改均使用 py_compile + 定向 pytest，但"改后跑哪一层测试（unit/integration/并发回归）"尚未形成固定决策树 | 所有 apps/api 改动 | pytest tests/unit、tests/integration、conftest.py 真实服务夹具；无需 MCP | Planned（再跑 1 次后端 Feature 即可升 Pilot） |
| **D1 figma-to-code** | D | 全仓库无 Figma 引用、无设计系统接入 | — | — | Do Not Create |
| **D2 通用 CRUD 模块脚手架** | D | 四件套（router/service/repository/schemas）规范已在 layering.md，数量有限且每个模块业务差异大，模板化收益低，backend-engineer + Rule 足够 | — | — | Do Not Create |
| **D3 JWT/认证功能实现 Skill** | D | F1.2 黑名单校验是一次性整改，authentication.md 已承载约束，不构成重复流程 | — | — | Do Not Create |
| **D4 Git 提交/分支助手** | D | 一次性决策多，无稳定输出，普通 Prompt 即可 | — | — | Do Not Create |
| **D5 架构问答/规则检索 Skill** | D | 14 条 Rule 始终生效即回答"必须怎样"；Skill 与 Rule 重复建设 | — | — | Do Not Create |

---

## Why Skill

本项目的高价值重复不是"某段代码怎么写"（那是 Rule 的职责），而是**带产物模板、门控检查清单和固定工具序列的程序性工作**：

1. **门控流程有稳定形态**：F3.1 已证明一个 Feature 从选型到关闭存在固定 9 环节，输入是 Backlog 条目，输出是 `docs/features/<id>/` 标准产物，且每个环节有 PASS/FAIL 判定——这正是 Skill 的形态，普通 Prompt 每次都要重述流程，容易漏环（如漏掉 review 或 closing 状态更新）。
2. **环境编排成本高且可复用**：S2 每次小程序验证都要重复"Docker → API → H5 → token 注入 → 浏览器"一长串命令和已知坑（H5 无微信登录、token 须走 API 注入、uni storage 底层是 localStorage），封装后可避免每次重新踩坑。
3. **质量守卫需要机械化执行**：S3 的 diff 白名单核对、逐文件编译验证是用户既定工程惯例（已跨 membership/booking/miniapp 三次场景出现），但靠人工记忆会漏（F3.1 就暴露出预存改动污染 diff 的问题，正是守卫流程要捕获的）。
4. **跨 Agent 协作需要可复用编排**：S4/S6 的多 Agent 分工与对账手法已在真实任务中成形，值得从一次性 Prompt 沉淀为可重复调用的程序。

## Why Not Rule

`.trae/rules/` 与 Skill 的边界：

- **Rule 回答"必须成立什么"**（不变量、禁区、架构约束），以 alwaysApply/globs 常驻上下文，适合一句话到几段话的强制项，例如"Tool 只能调 Service""集合端点不加尾斜杠"。
- **Skill 回答"按什么步骤做完一件事"**，是按需调用的多步骤程序，包含：环境命令序列、文档模板、报告格式、判定决策树、浏览器操作编排。把这些放进 Rule 会让常驻上下文膨胀，且 Rule 无法承载脚本/模板资产，也没有"执行→产出→验证"的时态语义。
- 具体地：S1 的 9 环节流程若进 Rule，会与 `multi-agent-collaboration-v3.md`（Agent 间协作协议：谁负责/Handoff/Reconciliation）形成重叠——v3 是**协作关系协议**，S1 是**产物驱动的交付流水线**，两者引用而不合并；S2/S3 依赖具体命令与工具，明显是程序性而非约束性内容；S6 的强制项（四关校验）已在 `.trae/rules/ai/mcp.md`，Skill 只承载"新增一个 Tool 的执行步骤与测试编排"，不复制规则原文。

## Required Agent

| Skill | 主要使用者 | 协作 Agent |
|-------|-----------|-----------|
| S1 feature-delivery-lifecycle | 主 Agent（总控）编排 | 按 Feature 域调用 architect/frontend/backend/database/mcp |
| S2 miniapp-runtime-smoke-test | frontend-engineer | browser_use（验证执行） |
| S3 minimal-change-guard | 全部 Agent（改动后自检） | 主 Agent 复核 |
| S4 parallel-domain-audit | project-architect / 主 Agent | 5 专业 Agent 并行 |
| S5 spec-vs-code-reconciliation | project-architect | 对应域 Agent 提供证据 |
| S6 mcp-tool-onboarding | mcp-engineer | backend-engineer（Service 能力补齐）、database-engineer（必要时） |
| S7 rbac-permission-matrix | backend-engineer | project-architect（动作语义校准） |
| S8 alembic-migration-authoring | database-engineer | backend-engineer（回填逻辑） |
| S9 backend-change-verification | backend-engineer | — |

## Required MCP

**所有候选 Skill 均不依赖外部 MCP Server。**

- 当前项目唯一 MCP 是后端内部的 FastMCP（stdio，不暴露网络），它是**被开发/被测对象**，不是 Skill 运行所需工具。
- S2 的浏览器能力来自 Agent 内置 browser 工具；S4/S5 的代码调查来自内置搜索/读取工具；S7 如建端点枚举脚本，解析 OpenAPI JSON 即可，无需 MCP。
- 未来若引入专用 MCP（如设计稿、压测平台），再重新评估 D1（figma-to-code）。

## Required Resources

| Skill | templates | examples | scripts |
|-------|-----------|----------|---------|
| S1 | 9 份 Feature 文档骨架（requirement/user-flow/acceptance/plan/report×3/review/release-note） | F3.1 全套（已存在，直接作参照样板） | — |
| S2 | runtime-test-report 模板（TC 七要素 + PASS/FAIL/BLOCKED/UNKNOWN） | F3.1 runtime-test-report.md | 环境拉起脚本（docker compose up / uvicorn / dev:h5）、API 登录取 token + localStorage 注入片段 |
| S3 | static-verification 模板（AC 逐条表） | F3.1 static-verification.md | 改动守卫命令序列（status/diff 四件套/numstat）+ py_compile / vue-tsc 计数对比 |
| S4 | 5 Agent 审计 Prompt 模板 + 5 份交付文档骨架 | docs/delivery/ 现有 5 份 | — |
| S5 | Conflict 记录卡片（Conflict/Evidence/Impact/Recommendation） | F3.1 implementation-plan.md Conflict 节 | — |
| S6 | 新 Tool 检查清单（四关 + Service 先行 + 幂等 + PII + 测试清单） | ai-course-query 三份 implementation 文档、mcp-test-v1.1.md | 新 Tool 的 pytest 用例骨架 |
| S7 | 权限矩阵表模板（端点 / method / 资源:动作 / 角色 / 现状装饰器） | — | OpenAPI 端点枚举 → 矩阵初稿脚本（待建） |
| S8 | 迁移检查清单（down 可逆 / 多租户回填 / 锁与超时 / merge head 处理） | 27 个存量迁移中的正例待筛选 | alembic revision 生成与验证命令序列 |
| S9 | 测试层级决策树（改动类型 → unit/integration/并发回归） | booking/membership 修复的测试实践 | pytest 分层执行命令 |

---

## 建议的落地顺序

1. **先封装 S1 + S3**（F3.1 刚验证、记忆最强、对后续 P0 修复立刻有用），S2 可作为 S1 的内嵌环节或紧随其后。
2. F1.1 启动前，先做 **S7**（Planned → 至少 Pilot），它是 F1.1 的硬性前置。
3. F5.1 启动时把 **S6** 从 Pilot 升 Stable（用写操作 Tool 补齐验证）。
4. S4/S5 在下一次 Phase/Epic 审计中再验证一轮后固化。
