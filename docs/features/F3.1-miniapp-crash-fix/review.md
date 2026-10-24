# F3.1 — miniapp 运行时崩溃修复 · Feature Review

> Feature ID：F3.1
> 评审人：project-architect
> 评审日期：2026-09-26
> 评审性质：纯评审，未修改任何业务代码；本文件为唯一产出
> 评审输入：requirement.md / user-flow.md / acceptance.md / implementation-plan.md / implementation-report.md / static-verification.md / runtime-test-report.md + 评审人独立执行的 git diff 与源码核查

---

## Scope Review

**结论：严格遵守 F3.1 Scope。**

评审人独立执行 `git diff` 核查（非仅信文档）：

| 文件 | diff 实证 | 判定 |
|------|----------|------|
| `apps/miniapp/src/pages/teacher/schedule/index.vue` | 仅 +1 行：`import { extractList } from '@/utils/helpers'`（L108 `formatDateTime` 行之后） | ✅ 与 plan Exact Fix 一致 |
| `apps/miniapp/src/pages/teacher/students/index.vue` | 仅 +1 行：`import { extractList } from '@/utils/helpers'`（L91 之后） | ✅ 同上 |
| `apps/miniapp/src/pages/student/schedule/index.vue` | numstat +36/-10。其中 F3.1 部分仅 L148 一行：`@/api` 导入追加 `tenantApi`；其余为预存的 `validateCardForSchedule` 区域改动（L369-444） | ✅ F3.1 部分与 plan 一致 |

- 未触碰业务逻辑 / API / DB / MCP / UI / 样式，与 requirement.md §4 Scope 完全对齐。
- `git status` 确认 `apps/miniapp/src/utils/` 与 `apps/miniapp/src/api/` 无任何修改——`helpers.ts`、`api/index.ts` 未被改动（AC-1.5 成立）。
- Out of Scope 项（F3.2 类型清零、F3.4 四态、死代码清理、AiAssistant）均未越界实施。
- 工作区 `apps/miniapp/src/pages/` 下另有 2 个 modified 文件（`student/booking-confirm/index.vue` +258 行区域、`student/membership/index.vue` +29 行），经 grep 确认其 diff 不含 `extractList` / `tenantApi` 相关 import，属预存历史改动（static-verification.md §1.1 已声明），非 F3.1 引入。

## Architecture Review

**结论：无架构影响，符合全部架构规则。**

- 分层：改动为纯 import 补全，不涉及 Router / Service / Repository 任何一层；调用链维持 页面 → `src/api/index.ts`（小程序唯一请求层）→ 后端 HTTP API，符合 `architecture/architecture.md` 系统边界第 1、5 条。
- 契约：无 OpenAPI / `api-types` / `api-client` 变更，消费的端点（`teacherApi.getSchedules`、`bookingApi.list`、`tenantApi.getSettings`）均为既有端点，无契约漂移风险（R5 不触发）。
- AI/MCP：不涉及，`AiAssistant` 组件未改动，Gate（R6）不触发。
- 安全：鉴权（`checkLogin`、401 refresh）与租户头链路均为既有，未新增前端组装身份参数的行为。
- Agent Selection 符合 v3 §1：单端纯前端修复仅召 frontend 域，未空召 backend/database/mcp，无"召之即来"空转。

## Code Review

**结论：最小 import 修复，符号与源实现精确匹配，无隐藏业务逻辑变化，无无关重构。**

评审人独立核对导入符号源文件：

1. `extractList`：[helpers.ts:L29-81](file:///Users/lixiang/Desktop/class_booking_system/apps/miniapp/src/utils/helpers.ts#L29-L81) `export function extractList<T = any>`，覆盖数组 / `data.items` / `data.list` / 嵌套 `data` / 任意数组属性 5 种信封形态，兜底返回 `[]`——与 3 处调用点（`teacher/schedule` L191、`teacher/students` L134/L153）传入的 `{code,msg,data}` 信封实参兼容。
2. `tenantApi`：[api/index.ts:L538-545](file:///Users/lixiang/Desktop/class_booking_system/apps/miniapp/src/api/index.ts#L538-L545) `export const tenantApi = { getSettings() → request("/tenant/settings"), ... }`——与 [student/schedule/index.vue:L570](file:///Users/lixiang/Desktop/class_booking_system/apps/miniapp/src/pages/student/schedule/index.vue#L570) 的无参调用 `await tenantApi.getSettings()` 匹配。
3. import 风格逐文件对齐：教师两页单引号无分号、学员页双引号带分号且 `tenantApi` 按字母序置于末尾，未引发格式噪音（`git diff --check` 退出码 0）。
4. 三个崩溃点的 try/catch 上下文抽查与 plan 一致（如 [teacher/schedule/index.vue:L181-195](file:///Users/lixiang/Desktop/class_booking_system/apps/miniapp/src/pages/teacher/schedule/index.vue#L181-L195)、[student/schedule/index.vue:L569-581](file:///Users/lixiang/Desktop/class_booking_system/apps/miniapp/src/pages/student/schedule/index.vue#L569-L581)），补 import 后执行路径不变、无逻辑分叉。
5. 无顺手修复、无整文件格式化、无死代码清理——`git diff` 逐行确认 F3.1 部分仅含 import 行。

**隐藏业务逻辑变化：无。** 学员页 diff 中的 `validateCardForSchedule` 改动为 F3.1 实施前的预存未提交修改（已通过 diff 内容与 static-verification.md §5 交叉确认），不计入本 Feature。

## Regression Review

**结论：回归风险极低。**

- 修复机制：仅将"自由变量运行时 ReferenceError"变为"模块静态导入"，不改变任何运行时值语义；两个符号均被多个其他页面生产使用（plan §Why Import Fix Is Sufficient 列举了 6+3 个既有引用方）。
- 构建：`npm run build:mp-weixin` 构建成功，产物中符号引用有效（AC-2.1/2.2 PASS）。
- 类型：`vue-tsc` 错误数 30+ → 27，目标符号相关错误清零，无新增（AC-2.3 PASS）。
- 运行时（H5）：3 个页面控制台均无 `extractList is not defined` / `tenantApi is not defined`，无新引入的未捕获异常。
- 残余风险集中在"页面首次真正跑通数据加载后暴露下一层问题"（plan 中评级为中的既定风险），属验收观察项而非修复缺陷，按 Scope 约定发现后登记独立缺陷。

## Acceptance Review

| 用例组 | 判定 | 依据 |
|--------|------|------|
| AC-1.1 / 1.2 / 1.3 | **PASS** | 评审人 git diff 亲验：3 个 import 存在、路径与符号正确 |
| AC-1.4 | **条件 PASS** | 字面 `git diff` 口径 FAIL（学员页混入预存改动），但**本次 Feature 引入的改动**口径 PASS；预存改动非 F3.1 责任，处置权在用户（见 Risks R1） |
| AC-1.5 | **PASS** | F3.1 变更文件数 = 3 且均为目标页面；`helpers.ts` / `api/index.ts` 未改动（git status 亲验） |
| AC-2.1 / 2.2 / 2.3 | **PASS** | static-verification.md 证据充分，与 plan 预期一致 |
| AC-3 ~ AC-7（运行时） | **部分验证 + 6 UNKNOWN** | 见下方映射复核 |

**runtime-test-report 与 acceptance.md 映射复核（17 PASS / 0 FAIL / 6 UNKNOWN）：**

- 计数内部一致：4+3+2+4+4 = 17 PASS，3+0+1+1+1 = 6 UNKNOWN，0 FAIL，与报告汇总表吻合。
- **编号错位（文档缺陷，非代码缺陷）**：runtime-test-report 的"AC-3 学员排期页"实际对应 acceptance.md 的 **AC-5**（学员排期页）；acceptance.md 的 **AC-3（教师排期页）在 runtime 报告中没有独立用例组**——该页仅出现在 TC-6.4（未登录拦截，未进入数据加载）与 TC-7.1（控制台清扫）中。且按 plan Conflict #2 的警示，教师页异常会被既有 try/catch 吞掉，"控制台无 error"对该页 extractList 真实执行属弱证据；强证据目前由静态验证（vue-tsc 符号解析清零 + 产物引用抽查）与同类页面 teacher/students 的运行时 PASS（TC-4.2/4.3 同款 extractList 模式）承担。
- **6 项 UNKNOWN 均为 H5 环境保真度限制，无一指向修复缺陷**：TC-3.4/3.5/3.6（loading/空态/错误视觉态，uni 组件 H5 降级渲染差异）、TC-5.2 运行时降级复现（需网络层精确拦截时序）、TC-6.5（角色不匹配依赖微信登录链路的 role 写入）、TC-7.5（异步销毁需精确时序）。
- acceptance.md 中尚无运行时证据的条款（需在 DevTools 人工验收关闭）：AC-3.2~3.6（教师排期页数据渲染/周切换/空周/详情/断网）、AC-4.4~4.8（切换排期/状态文案/两种空态/断网）、AC-5.3（租户配置生效为 60 分钟，依赖后端可配置环境）、AC-5.5/5.6（预约跳转/无卡拦截）、AC-5.7/5.8、AC-6.2（角色不匹配，对应 TC-6.5 UNKNOWN）、AC-7.1（快速切页，对应 TC-7.5 UNKNOWN）。

## Risks

| # | 风险 | 等级 | 处置建议 |
|---|------|------|---------|
| R1 | 学员页预存改动（`validateCardForSchedule` +36/-10 中的非 import 部分）与 F3.1 混在同一工作区文件，若整文件提交将污染 F3.1 commit 粒度 | 中 | 提交时由用户确认归属后拆分（`git add -p` 或先提交预存改动）；AC-1.4 按"本次会话改动"口径判 PASS |
| R2 | acceptance AC-3（教师排期页）无运行时数据渲染证据，存在"静态通过但首跑暴露下游问题"的残余风险 | 中 | DevTools 人工验收时按 AC-3.1~3.6 逐条执行；发现新问题登记独立缺陷，不回灌 F3.1 |
| R3 | 其余 5 项 acceptance 条款缺口（AC-4.4~4.8、AC-5.3/5.5~5.8 等） | 低 | 同属 DevTools 人工验收既定范围（acceptance.md 指定的验收环境本就是微信开发者工具） |
| R4 | runtime 报告 AC 编号与 acceptance.md 错位，后续追溯可能误读 | 低 | 文档勘误项，建议随验收关闭时一并修正编号，不阻塞 |

## UNKNOWN

| # | 项 | 性质 | 下一步 |
|---|----|------|--------|
| U1 | 6 项 H5 保真度 UNKNOWN（视觉态 ×3、降级复现、角色拦截、异步销毁） | 环境限制，非修复缺陷 | 微信开发者工具人工复核 |
| U2 | acceptance AC-3.2~3.6 / AC-4.4~4.8 / AC-5.3 / AC-5.5~5.8 无运行时证据 | 验证覆盖缺口 | 同上，DevTools 验收执行 |
| U3 | `tenantApi.getSettings()` 返回类型 `{}` 导致 L572 存量 TS 报错，运行时取值正确性 | 存量类型债务 | AC-5.3 人工验证；类型清零属 F3.2 |
| U4 | 学员页预存改动归属与意图 | 待用户决策 | 用户确认后决定提交策略 |
| U5 | 剩余 27 个存量 TS 错误 | 历史债务 | F3.2 Scope，不在本 Feature |

## Recommendation

1. **代码层面**：F3.1 修复正确、最小、完整——3 个崩溃点（`extractList` ×2 文件、`tenantApi` ×1 文件）均已通过"静态符号解析 + 构建产物 + H5 运行时无 ReferenceError"三重证据确认解决，无需任何代码返工。
2. **验收层面**：剩余工作全部是 acceptance.md 既定的人工验收执行（微信开发者工具），非修复缺陷。建议 DevTools 复核清单：6 项 UNKNOWN + 上文列出的 acceptance 条款缺口，重点补 AC-3 教师排期页的运行时数据渲染证据。
3. **提交层面**：先将学员页预存改动与 F3.1 import 行拆分提交（或确认归属），避免污染 F3.1 变更粒度。
4. **后续 Feature**：需要。F3.2（vue-tsc 类型门禁 + 27 个存量错误清零）已确认必要——本次事故根因正是构建链路无类型检查；微信开发者工具人工复核作为 F3.1 验收关闭的前置动作执行；F3.4（四态）维持 backlog 排期。
5. **文档勘误**（不阻塞）：runtime-test-report 的 AC 编号与 acceptance.md 对齐；requirement.md/user-flow.md 中"页面加载即崩/阻断后续全部加载"的措辞按 implementation-plan.md Conflict #1/#2 的真实代码结论修正。

**最终结论：READY_FOR_ACCEPTANCE**
