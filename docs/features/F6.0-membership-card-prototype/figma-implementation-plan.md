# F6.0 会员卡原型 → Figma 实施方案（可行性评估与执行计划）

> 日期：2026-10-16
> 类型：**检查与方案设计**（本次不重写 HTML、不改业务代码、不创建 Figma 文件）
> 输入依据（均按磁盘实际文件核对，未假设与文档描述一致）：
> `prototype/index.html`、`figma-creation-guide.md`、`screen-inventory.md`、`interaction-spec.md`、
> `business-rules.md`、`entity-state-model.md`、`open-decisions.md`、`prototype-acceptance.md`、
> `prototype-validation-report.md`、`prototype-visual-diff.md`、`verify-prototype.js`
> 环境探测：`~/.trae-cn/mcps/**`、`~/.trae-cn/plugin-config.json`、环境变量、`/Applications`、全局 npm

---

## 0. 结论速览（TL;DR）

- 现有 `prototype/index.html` 是**单文件、零外部依赖**的 HTML 原型，14 个页面 + 9 个弹窗，用全局 `STATE` + 函数式重渲染切换页面，**可脚本化验证且当前 121/121 断言全通过**。
- **本环境不具备"创建 Figma 文件"的能力**：唯一配置的 `mcp_Figma_AI_Bridge` **只有 2 个只读工具**（`get_figma_data` / `download_figma_images`，方向是 Figma → 代码），无写型 MCP、无 Figma token、无 Figma CLI、未安装 Figma 桌面版。
- 因此**"用 MCP 直接生成 Figma"（方案 C）在本环境不可行**，只能作为创建后的回读校验通道。
- **推荐方案 B**：以现有规格文档为唯一事实源，**自动生成一个 Figma 插件**（Plugin API），由人工在 Figma 内导入运行，一次性产出 Pages / Variables / Text&Effect Styles / 带 Variant 的 Component / Screen Frame / 决策便签 / Prototype 反应；再用只读 MCP 回读校验。
- **重要前置风险**：`figma-creation-guide.md`（2026-10-10）**已明显落后于原型 v8（2026-10-16）**，其 11 Page / 15 Frame / TabBar / 主色 / 管理端字段 / 决策便签口径均需先修正，否则按该指南做出的 Figma 会复刻一个过时版本（详见第二节）。
- **阻塞项（必须先解）**：Figma 账号与目标 File 的编辑授权、能否安装并运行 dev 插件、Variables 功能所需的付费席位。详见第五节。

---

## 1. 现有原型检查结果

### 1.1 工程形态

| 项 | 实测结果 | 证据 |
|---|---|---|
| 文件形态 | **单文件 HTML**，无拆分 | `prototype/index.html`（169,573 字节，唯一文件） |
| 外部依赖 | **零**：无 `<link>`、无 `src=`、无 `@import`、无 srcset | 全文仅 1 处 `<script>`（第 582 行），无外部引用 |
| 脚本结构 | 单个内嵌 `<script>`，纯 vanilla JS，无框架 | 第 582 行起 |
| 样式 | 全部内联 `<style>`，含令牌化的 CSS 变量与组件类 | 第 75–765 行区间 |
| 数据 | 全内存 mock（`BASE_CARDS/BASE_TXNS/BASE_BOOKINGS/S1_ROSTER`），不发 HTTP | `STATE` 初值第 666 行 |
| 运行方式 | 浏览器直接打开即可（无需构建、无后端） | — |

### 1.2 页面切换机制（**单页多状态，非多 HTML 文件、非 iframe**）

- 中央状态对象 `STATE = { view, adminPage, stuPage, teacherSched, stuTab, bookTab, ... }`（第 666 行）。
- 视图切换：`setView(v)`（第 820 行）在 `dual | admin | student | teacher` 间切。
- 管理端：`goAdmin(p)` / `renderAdminPage()`（第 855–865 行）按 `adminPage` 派发。
- 学员端：`goStu(p)` / `stuTab(p)` / `renderStuPage()`（第 1303–1321 行）按 `stuPage` 派发。
- 教师端：`renderTeacher()`（第 1905 行附近）。
- 弹窗：`openModal()/closeModal()` + `mask` 遮罩，配合 11 个弹窗构造函数。
- **判断结论**：属「**单页 + 按状态重渲染**」模式；弹窗以 Overlay 模拟，非独立页面文件。

### 1.3 实际实现的页面 / 弹窗 / 组件 / 状态（**以源码为准**）

**页面（共 14 个 Screen）**

| 端 | 页面 | 派发证据 |
|---|---|---|
| admin | P-A1 卡产品管理 | `adminA1()` L868 |
| admin | P-A2 会员卡管理列表 | `adminA2()` L950 |
| admin | P-A5 预约管理列表（**待新增**，侧栏 `added:true`） | `adminA5()` L1189 |
| admin | P-A6 排期签到点名 | `adminA6()` L1214 |
| miniapp | P-M8 首页·课程列表 | `stuM8()` L1327 |
| miniapp | P-M9 我的·个人中心 | `stuM9()` L1355 |
| miniapp | P-M10 AI 助手（一级 Tab） | `stuM10()` L1448 |
| miniapp | P-M1 我的会员卡列表 | `stuM1()` L1483 |
| miniapp | P-M2 卡详情+使用记录 | 派发 L1315 |
| miniapp | P-M3 课程排期选择 | 派发 L1316 |
| miniapp | P-M4 预约确认选卡 | 派发 L1317 |
| miniapp | P-M5 预约结果页 | `stuM5` 派发 L1318 |
| miniapp | P-M6 我的预约 | `stuM6()` L1830 |
| teacher | P-T1 教师排期名单签到 | `renderTeacher()` L1905 |

**弹窗 / Overlay（共 9 个）**：`openProductModal`（P-A1 新建/编辑）、`openIssueModal`（P-A3 发卡）、`openCardDetail`（P-A4 卡详情+流水）、`openBatchDeleteProducts`、`openBatchCancelCards`、`openFreezeModal`、`openRenewalModal`、`openConflictModal`、`openCancelModal`（P-M7 取消确认）；另有通用 `openModal/closeModal`。

**组件类（真实复用或自建，节选）**：`.card-status-badge`+`.badge-dot`、`.credits-display`、`.card-selector-popup`、`.filter-tabs`、`.stu-tabbar`+`.tab-indicator`、`.stu-backbar`、`.desc-grid`（el-descriptions 网格）、`.pending-banner`、`.tch-head`/`.tch-row`、`.ai-bubble`/`.ai-dots`、`.sticky`（黄色未确认便签）、`.cnote`（绿色已确认便签）。

**决策便签现状（关键）**：`.sticky`（黄）与 `.cnote`（绿）两种并存，共 21 处引用。**D1/D3/D4/D5/D9 已确认**（`open-decisions.md` 决策记录表确认日期 2026-10-16）→ 用绿色 `.cnote`；**D2/D6/D7/D8 待确认** → 用黄色 `.sticky`。

**四态覆盖（**不完整**）**：仅有空态（`.empty`）与错误态（`errorState()` L786）；**全文无 loading / skeleton 状态**（`loading|skeleton|加载中|重试` 仅 5 处且均为文案级）。→ `prototype-acceptance.md` AC7「四态齐备」在 HTML 原型中**未达成**（属 Figma 阶段需补的增量）。

### 1.4 可运行性

- **可脚本化验证通过**：`node verify-prototype.js` → `[1] SYNTAX OK`、`PASS 121 / FAIL 0`、`EXIT=0`（覆盖 [A]–[K] 共 121 条，含真实调用页面函数的副作用断言）。
- 该脚本以 `new Function` 做语法检查 + DOM stub 下真实调用函数，证明脚本可被 JS 引擎解析且核心流程可用；**未做真实浏览器渲染截图**（环境限制，脚本内已声明）。

### 1.5 现有 HTML 与 Figma 设计稿之间的差距（结构性）

| 差距维度 | HTML 原型现状 | Figma 目标 | 处理方式 |
|---|---|---|---|
| 图层模型 | 一个浏览器 DOM 树，状态切换重渲染 | 原生 Frame/Component/Variant 图层树 | 需重建，html-to-Figma 插件难还原语义 |
| 状态组织 | 同页多状态由 JS 切换（点击即变） | Variant / Change To 交互表达 | 映射到 Variant + Prototype reaction |
| 令牌 | CSS 变量 + 内联样式 | Figma Variables + Text/Effect Styles | 需从源码抽取生成 |
| 交互 | 真实 JS 逻辑（预约/取消/签到改数据） | 仅 Prototype 连线（不跑业务逻辑） | 仅保留"可点击可达"路径，逻辑不迁移 |
| 四态 | 仅空/错误，缺 loading | AC7 要求四态齐备 | Figma 阶段补齐为变体 Frame |
| 决策便签 | 黄/绿两类已落地 | 需同款两类 Component | 生成两类 sticker 组件 |

---

## 2. 实际页面与目标页面差异表

### 2.1 规格文档自身不一致（**必须先对齐**）

| 项 | `figma-creation-guide.md` 声称（2026-10-10） | 磁盘实际（原型 v8 / 2026-10-16） | 结论 |
|---|---|---|---|
| Figma Page 数 | 11（00–10） | 结构仍适用 | **一致** |
| Screen Frame 数 | 正文称 **15**（`3.1–3.14` 实际只枚举 **14**：P-A1\~A6 / P-M1\~M7 / P-T1） | 实际 **14 页面 + 9 弹窗**，且**新增 P-M8/P-M9/P-M10** | **不一致**：①"15"与自身枚举矛盾；②缺首页/我的/AI 助手 3 页 |
| 可复用组件 | 10（`2.1–2.10`） | 现需 ≥11（新增"已确认便签"绿色款） | **偏差** |
| admin Frame | 1440 × 900 | 一致 | **一致** |
| miniapp Frame | 375 × 812 | 一致 | **一致** |
| 流程 A–G | 7 条 | 一致 | **一致** |
| 待开发 API | 灰置 + 占位 | 原型用 `disabled/灰置/待开发/待新增`（55 处） | **一致（原则）** |

### 2.2 内容级差异（指南落后于原型的部分）

| # | 项 | 指南（旧） | 原型 v8（新，应为准） | 影响 |
|---|---|---|---|---|
| 1 | 小程序底部 TabBar | 4 Tab「课程/我的预约/会员卡/我的」；选中 **#07c160**；图标 24×24 | 4 Tab「**首页/排期/AI 助手/我的**」；选中 **#8b7355**；**真实线性 SVG** | TabBar 组件需重定义 |
| 2 | 小程序主色 | `color/primary-miniapp = #07c160`（微信绿） | **香槟金 `#C9A66B`**（含 `--gold-d/#B8956A`、`--gold-l/#DBC18A`） | 整份 token 需改 |
| 3 | P-A1 字段 | 含**「每周上限」「状态」「回收站/恢复」** | v7 已**删除**（真实 `card-types/index.vue` 无此字段/入口） | P-A1 Frame 需重画 |
| 4 | P-A2 状态文案 | 「使用中/已用尽」 | 管理端＝**未激活/正常/已过期/已冻结/已作废**；学员端才用"使用中/已用尽" | StatusBadge 需按端分变体 |
| 5 | StatusBadge ACTIVE | 文案「使用中」（未分端） | 管理端「正常」、学员端「使用中」 | 需 2 套文案 |
| 6 | P-A3 字段 | 含「**重复发卡策略开关**」 | 真实无此开关（改由「续卡提示」409 弹窗驱动） | P-A3 需删该控件 |
| 7 | P-A4 形态 | **1440×900 独立页**（上信息卡+下流水表） | 实际为**卡详情弹窗**（`el-descriptions` 两列网格 + 流水"原型扩展"标注） | Frame 尺寸/所属 Page 需改 |
| 8 | DecisionSticker | **只有黄色**未确认款（D1–D9 全体贴黄） | 需**两款**：黄（D2/D6/D7/D8）+ **绿"已确认"（D1/D3/D4/D5/D9）** | 组件需加 Variant |
| 9 | D1/D3/D4/D5/D9 处理 | 一律黄色占位、禁止画成定论 | **已确认 2026-10-16** → 应画成**确定性交互** | 与 AC5/红线 4 的表述冲突，需改写 |
| 10 | 新增页面 | 无 P-M8/P-M9/P-M10 | 已实现首页、我的、AI 助手一级 Tab | Page 04/05 需扩容 |
| 11 | 四态 | AC7 要求四态齐备 | 原型仅空/错误，**缺 loading** | Figma 需补 loading 变体 |

> **红线提示**：指南第 12 行"未确认决策位置一律放黄色便签" + AC5/红线 4 在 **v8 之后已部分失效**（D1/D3/D4/D5/D9 已确认）。按旧指南执行会把**已确认规则错标成占位**，同样违反一致性要求。必须先把"已确认项画成确定交互、仅 D2/D6/D7/D8 保留黄色占位"写成新版口径。

---

## 3. 三种转换方案比较

> 前提：**本环境未预装/未授权任何可"创建" Figma 内容的工具**（已实测，见第五节）。下表按"若补齐相应条件后"的能力评估。

| 维度 | **A. HTML→Figma 插件**（如 html.to.design） | **B. Figma Plugin API（自建插件）**（+ REST 只读校验） | **C. Figma Design MCP / 已配置集成** |
|---|---|---|---|
| 能否用现有 HTML | **可**：把 HTML 渲染后导入（单文件需逐页驱动后分别导入） | **间接**：HTML/文档作为规格来源，生成插件代码，不直接导入 | **不可**（本环境工具只读） |
| 可编辑图层 | **部分**：多为绝对定位 group/frame，非 auto-layout，层级噪声大 | **是**：`createFrame/createText` 等原生节点 | 不适用 |
| Component / Variant | **通常不产出**（个别插件仅能映射到库内同名组件，成功率低） | **是**：`createComponent` + `combineAsVariants` | 不适用 |
| Variables | **否** | **是**：`figma.variables.*`（需付费席位启用 Variables） | 不适用 |
| Prototype 连线 | **基本不支持**（个别插件链接不稳定） | **是**：节点 reaction（`setReactionsAsync` 等）；连线本身属 FigJam | 不适用 |
| 是否需要人工调整 | **大量** | **中**（生成后微调；须人工在 Figma 内运行插件） | — |
| 账号/工具/权限 | Figma 账号 + 安装插件（html.to.design 需付费）+ 目标文件 Edit 权限 | Figma 账号（桌面/网页）+ 目标 File 编辑权 + **在 Figma 内运行 dev 插件** + Variables 需付费计划 | **无**（本环境无写型工具/token，见 5.3） |
| 主要限制/风险 | 无法满足 AC1–AC10；图层不可维护；组件/Variables/连线缺失 | REST **无写接口**，必须走插件；插件需人工导入执行；Variables/reaction API 受计划与版本限制 | **完全阻塞创建**；仅能 Figma→代码方向 |
| 满足 AC1–AC10 能力 | **低** | **高**（唯一可全覆盖路径） | 不适用 |

### 3.1 方案 A 详评

- 优点：上手快，能"看到"HTML 的视觉。
- 致命短板：①**无语义组件**（AC1–AC10 要求的组件/Variant/变量/连线几乎全缺）；②图层为绝对定位噪音，后续无法维护；③原型为**单文件 JS 切页**，导入前须逐页驱动渲染，工作量与风险都高；④**属付费插件**且本环境未安装授权。
- 适用：仅作**视觉参考的快速 bootstrap**，不作为交付路径。

### 3.2 方案 B 详评

- 唯一能同时满足：原生可编辑图层 + Component/Variant + Variables + Prototype 反应的路径。
- 事实要点：**Figma REST API 对文件内容为只读**（`GET /v1/files`、`/nodes`、`/images`），**没有公开的"创建节点"REST 端点**；创建必须依赖**在 Figma 内运行的 Plugin API**。
- 因此 B 的闭环 = 「本地生成插件代码 → 人工在 Figma 导入并运行 → 产出文件 → 只读 MCP 回读校验」。

### 3.3 方案 C 详评（本环境实测）

- `mcp_Figma_AI_Bridge` 已配置于 `~/.trae-cn/mcps/s_class_booking_system-efb09230/browser_use/mcp_Figma_AI_Bridge/`，**仅含 2 个工具**：`get_figma_data`、`download_figma_images`。
- 两者语义均为**读取/下载已存在的 Figma 文件**（Figma → 代码方向）。
- **结论：C 无法创建 Figma 文件/组件/连线**；本环境 `FIGMA_*` 环境变量为空、无 Figma CLI、`/Applications` 无 Figma、全局 npm 无 figma 包。
- 可用价值：作为**方案 B 产出后的回读与差异校验通道**。

---

## 4. 推荐方案及理由

### 推荐：**方案 B 为主 + 方案 C 作校验**（方案 A 仅作可选 bootstrap）

理由：
1. **只有 B 能覆盖验收项**：Component/Variant（AC2/AC3）、Variables/Token（指南第 6 节）、四态变体（AC7）、Prototype 连线（AC1）、决策便签（AC5）。
2. **符合"以规格文档为唯一事实源"**：本目录已有 9 份经审核规格（含 `ui-visual-spec.md` 第 6 节逐条带 `文件:行号`），可据此**生成**插件，避免凭空设计。
3. **闭环可控**：生成→人工运行→**只读 MCP 回读校验**，无需新增写型凭据，安全边界清晰。
4. **满足约束**：不改业务代码、不改业务规则；待开发 API 以"灰置 + 占位"图层表达；未确认决策以黄色便签、已确认以绿色"已确认"便签。

---

## 5. 工具与权限准备清单

### 5.1 已具备（本环境实测）

| 项 | 状态 | 证据 |
|---|---|---|
| F6.0 全部规格文档 + 原型 + 验证脚本 | ✅ 齐备 | 目录 18 个文件 |
| Node（运行验证脚本 / 生成插件） | ✅ 可用 | `node verify-prototype.js` 已通过 |
| `mcp_Figma_AI_Bridge`（**只读**） | ✅ 已配置 | `~/.trae-cn/mcps/.../mcp_Figma_AI_Bridge`（2 工具） |

### 5.2 需要人工/外部补齐（**阻塞项**）

| 项 | 用途 | 说明 |
|---|---|---|
| **Figma 账号 + 目标 File（建议新建空文件）+ Edit 权限** | 产出原生图层 | 必须先建成一个空 File 并拿到 `fileKey` |
| **Figma 桌面版或可运行 dev 插件的网页版** | 运行自建插件 | 插件 API 必须在 Figma 内执行 |
| **Figma 付费计划席位（Variables / 必要时团队库）** | 建立 Variables 与发布组件 | Variables 功能需付费计划；请确认账号计划 |
| （可选）**Figma REST Token（只读）** | 回读校验增强 | 现仅靠 MCP 只读工具，若需 REST 回读则需 token（只读即可） |
| （可选）**html.to.design 授权** | 方案 A bootstrap | 付费插件，非必需 |

### 5.3 当前明确阻塞（不能声称已完成的部分）

1. **无任何可创建 Figma 内容的工具授权**（MCP 只读、无 token、无 CLI、无桌面 App）→ 创建仍**必须由人工在 Figma 内运行插件**。
2. ~~无目标 Figma File / `fileKey`~~ **已解决**：`fileKey = Ovr4Zo8vPTohgqv9AZqIVr`（文件 `dance_v1`）。
3. ~~Variables 付费计划归属未确认~~ **已确认**：目标文件为 **Starter（免费）计划**，**不提供 Variables**，且 **Page 上限 = 3** → 插件已按紧凑模式适配（见 §7.1）。

> **2026-10-17 状态**：插件代码（含紧凑模式）+ 自检器已就绪。**在人工于 Figma 内实际运行并回读校验通过之前，仍不得声称已创建 Figma 文件 / 组件 / 连线**。

---

## 6. 分阶段执行步骤

### Phase 0 — 规格对齐（**必须先做**）

- 动作：把 `figma-creation-guide.md` 从 2026-10-10 口径升级到 v8 事实（改 11/15 Frame 口径为实际 14 页面+9 弹窗，纳入 P-M8/M9/M10；TabBar/主色/管理端字段/A4 形态/D 便签二分口径全部按第 2 节差异表修订）。
- 产出：修订版指南（含"已确认 D1/D3/D4/D5/D9 = 确定性交互；D2/D6/D7/D8 = 黄色占位"的新红线表述）。
- **不触发**任何业务代码/原型改动。

### Phase 1 — 生成机器可读规格（Spec JSON）

- 动作：从原型 + 文档抽取并固化：
  - `tokens.json`（颜色/字号/间距/圆角/阴影，按香槟金与 admin 双端）；
  - `components.json`（≥11 组件 + Variant 矩阵，含 StatusBadge 双端文案、Sticker 黄/绿两款、TabBar 四 Tab）；
  - `frames.json`（14 页面 + 9 弹窗的尺寸/所属 Page/字段/四态变体）；
  - `interactions.json`（指南第 4 节连线表 + 第 5 节流程 A–G）。
- 产出：`docs/features/F6.0-membership-card-prototype/figma-spec/*.json`（新增，纯规格，不含业务代码）。

### Phase 2 — 生成 Figma 插件

- 动作：生成 `figma-plugin/manifest.json` + `code.js`（开发态插件），实现：
  - 建 11 个 Page；② 建 Variables + Text/Effect Styles；③ 建 Component + Variant（含黄/绿便签、双端徽标、四 Tab TabBar）；
    （**注**：Page 数已因 Starter 计划改为 3 组紧凑模式，见 §7.1）
  - 建 19 个 Screen Frame + 10 个 Overlay Frame，按 `frames.json` 用 Instance 引用组件；⑤ 按 `interactions.json` 设置节点 reaction（Prototype）。
- 约束：`code.js` 只"画"不"跑业务逻辑"；待开发 API 一律用**灰置图层 + 占位标注**；未确认决策 D2/D6/D7/D8 用黄色便签组件。
- 产出：可导入的插件目录（本地文件，不写入 `apps/`）+ `figma-plugin/verify-plugin.js`（vm 桩自检器，`node verify-plugin.js` 退出码 0 = 全通过）。

### Phase 3 — 人工在 Figma 运行（**人工步骤**）

- 动作：在 Figma 中 `Plugins → Development → Import plugin from manifest`，加载 `figma-plugin/`，选择目标页面运行，产出 Figma 文件。
- 记录：`fileKey`、执行日志、生成结果截图。
- **2026-10-17 首次运行结果**：目标文件 `dance_v1`（`fileKey = Ovr4Zo8vPTohgqv9AZqIVr`）为 **Starter（免费）计划**，插件在 `createPage` 建第 4 个 Page 时报错
  `The Starter plan only comes with 3 pages. Upgrade to Professional...`，主流程整体中断，文件仅残留 3 个**空** Candidate Page（无 Frame / Component / 连线）。
- **处置**：按用户决定采用**降级为 Starter 兼容紧凑模式**（见 §7.1）。插件已改造为「复用既有 Page + 清空重建，仅在不足 3 个时才新建」，Page 数恒 ≤ 3，且每段 `try/catch` 独立续跑不再整体中断。

### Phase 4 — 回读校验

- 动作：用只读 `get_figma_data(fileKey)` 拉回生成结果，与 `figma-spec/*.json` 逐项比对（Page 数、Frame 尺寸、组件/变体数、Variables、便签数量与颜色、连线可达性）。
- 辅助：人工走查 `prototype-acceptance.md` 第六节演示脚本与 AC1–AC10 / 五条红线。

### Phase 5 — 交付登记

- 动作：把 `fileKey` 与 Figma 链接登记到本目录 README / Execution Board；状态标记 `READY_FOR_FIGMA`。

---

## 7. 每个阶段的验收标准

| 阶段 | 验收标准（通过条件） |
|---|---|
| Phase 0 | 指南与第 2 节差异表一致；无"已确认项被要求画成占位"的表述；无"待开发 API 画成可用"表述 |
| Phase 1 | 4 份 JSON 通过 schema 校验；组件数 ≥11；Frame 数 = 14 页面 + 9 弹窗；流程 A–G 全覆盖；D 便签二分正确（绿 5 / 黄 4） |
| Phase 2 | `code.js` 通过静态检查（`node --check`）；无网络请求；无对 `apps/` 的写入；灰置/占位逻辑存在于代码路径；`verify-plugin.js` 自检全通过（退出码 0） |
| Phase 3 | Figma 内运行无报错；**Page ≤ 3（紧凑模式，取代原「Page=11」）**；Frame 尺寸符合（admin/teacher 1440×900、miniapp 375×812、Overlay 自适应）；手动确认组件已生成；Variables 若计划不支持则已降级为 Styles |
| Phase 4 | 回读数据与 JSON 一致（差异项 ≤ 与人工核对表）；AC1–AC10 通过、五条红线无违反；AC7 四态（含**新增 loading**）齐备 |
| Phase 5 | 链接登记完成；状态置 `READY_FOR_FIGMA` |

### 7.1 紧凑模式修订（2026-10-17，Starter 计划适配）

**触发**：目标文件 `dance_v1`（`fileKey = Ovr4Zo8vPTohgqv9AZqIVr`）为 Figma **Starter（免费）计划**，**Page 上限 = 3 且不提供 Variables**。原插件按 11 Page 生成，在第 4 个 `createPage` 处报错并整体中断。

**修订内容**：

| 项 | 原设计 | 紧凑模式（现） |
|---|---|---|
| Figma Page 数 | 11（00–10） | **3**（复用既有 Page 原地重建，不足才新建） |
| Page 分组 | 按业务切分 11 组 | ①`01-管理端与教师端`（P-A1/A2/A5/A6 + P-T1 + 8 个管理端 Overlay）；②`02-学员小程序`（P-M1–M6/M8/M9/M10 + P-M7）；③`03-可复用组件`（9 组件集 + 1 单组件） |
| 空置 Page | 00/07/08/09 登记但无 Frame | 不再占用独立 Page（F-00-*/F-Flow-* 本就无尺寸规格、不产出） |
| OV-CONFIRM | 全局 1 个 | **各端页各 1 个**（管理端 / 小程序），确保 reaction 目标与源 Frame 同 Page、不跨页 |
| Variables | `figma.variables.*` | 不可用时**自动降级为 Color/Text/Effect Styles**（Starter 下即为 Styles） |
| 中断风险 | 单点失败整体中断 | 每段 `try/catch` 独立续跑；仅 Page 准备失败才终止 |

**落地计数（`node figma-plugin/verify-plugin.js` 实测，38/38 全通过）**：Page=3、Screen Frame=14、规范 Overlay=9（+2 脚手架）、组件集=9、单组件=1（顶层组件 10）、reaction=39、灰置占位=11；场景 A（既有 3 页）`createPage` 调用=0，场景 B（既有 1 页）仅新建 2 个。

> **`figma-spec/frames.json` 保持 11 Page 登记不变**（规格层事实源不动）；紧凑模式仅在 **Figma 落地层**把 11 组归并为 3 个 Page，属交付形态差异，已在本文档登记。

### 7.2 保真度决策（2026-10-18，从"结构骨架"升级为"中高保真 UI"）

**触发**：紧凑模式首次落地后，画布上仅"空 Frame + 标题标签 + `trigger:`/`disabled:` 小方块"，用户两次反馈与浏览器所见不符（先"完全不符合"，后"学员小程序不完善"）。

**决策与落地**：

| # | 决策 | 落地方式 |
|---|---|---|
| 1 | 插件补画真实 UI（**中高保真，非像素级**） | `code.js` 新增绘制引擎：三套 Shell（管理端侧栏 200 + 页头 48 / 教师端居中 560 卡片流 / 小程序状态栏 24 + 内容窗口）+ 基元（面板/文本/标签/徽标/按钮/表格/决策便签），**19 屏 + 10 弹窗**逐屏绘制 |
| 2 | **长页拆帧**（用户 2026-10-18 选择） | ① 首页内容高 **1300px**（含 2 个视频卡）> 可视窗口 **738px**（812 − 24 状态栏 − 50 TabBar）：拆为 `P-M8`（上半屏）+ `P-M8b`（滚动续帧，`offset = 738`，**不重叠**）；② P-M1 内容高 **1016px** > 窗口 **788px**（本页无 TabBar）：拆为 `P-M1` + `P-M1b`（`offset = 666`，对齐第 4 张卡结尾，避免卡片被折叠线切断）。`SPEC.scrollSplit` 登记 |
| 3 | TabBar 安全区 | 四个 Tab 页（P-M8/P-M3/P-M9/P-M10）内容窗口高度改为 `812 − 24 − 50 = 738`，内容不再被 TabBar 压住；续帧 P-M8b 保留 TabBar，P-M1b（源页非 TabBar 页）不带 |
| 4 | Overlay 高度按内容自适应 | frames.json 登记为 `auto`，落地取值：P-A3 `420x340`、P-A4 `660x520`、**OV-PRODUCT `420x620`**、OV-BATCH-DELETE `420x260`、OV-FREEZE `420x300`、OV-RENEWAL `420x300`、OV-CONFLICT `480x360`、OV-BATCH-CANCEL `420x320`、P-M7 `320x320`、**OV-CARDSEL `375x460`** |
| 5 | 连线不覆盖 UI | 触发按钮/灰置占位移出源 Frame，改为每个源 Frame 右侧一个 300px「交互热点」面板；网格 `GAP=340` 预留该槽位 |
| 6 | 已知缺字规避 | `☐`(U+2610) 在常用中文字体中易缺字 → 改用矢量方框；emoji 图标 → 改用首字圆角方块 |
| 7 | **元素级缺口补齐（2026-10-18 第二轮）** | 用户二次反馈"学员小程序还不完善"→ 按"内容缺失"口径做只读逐屏元素级比对，补 **5 个状态屏 + 1 个弹窗**：`P-M1c` 无效课卡 / `P-M1d` 空状态 / `P-M5b` 预约失败 / `P-M6b` 预约空态 / `P-M10b` AI 对话态 / `OV-CARDSEL` 选卡底部弹窗；并补内容：P-M1 卡片 6 张有效 + 2 张无效（含冻结/提前解冻）、P-M2 使用记录 4 条、P-M3 排期卡三态（预约/已满/取消+时限）、P-M5 期卡分支、P-M6 4 种记录态（含取消时限灰态与取消原因）、P-M8 第 2 个视频卡、P-M10 徽标行 + AI_QUICK 真实 4 问 |
| 8 | 连接补登 | 新增 `P-M4 → OV-CARDSEL`（点击「使用会员卡」打开选卡底部弹窗），非 `none` 连接 39 → **40** |

**实测（`node:vm` 桩真跑 `code.js`，统计每帧内容底边；桩内文本高度按单行估算，故为下界）**：

| 帧 | 帧高 | 内容底边 | 结论 |
|---|---|---|---|
| P-M8（上半屏） | 812 | ~1300 | 738 以上内容进续帧，窗口内不裁切 |
| **P-M8b（滚动续帧）** | 812 | 24+738+562 | 承接折叠线以下 562px（第 2 个视频卡），**无裁切** |
| P-M1（上半屏） | 812 | 1016 | 666 以上内容进续帧 |
| **P-M1b（滚动续帧）** | 812 | 24+666+350 | 承接第 5/6 张卡与便签 |
| P-M2 / M3 / M4 / M5 / M5b / M9 / M10 / M10b | 812 | 均 ≤ 738 | 均在窗口内，**无裁切** |
| P-M6（4 卡 + 双便签） | 812 | ~760 | 止于窗口 788 之内 |
| P-M6b / M1c / M1d | 812 | < 788 | 无裁切 |
| P-A1 / A2 / A5 / A6 / P-T1 | 1440×900 | 均 < 900 | 无裁切 |
| OV-PRODUCT | 620 | 554 | 底部按钮不再压"描述"输入框 |
| OV-CARDSEL | 460 | ~330 | 说明行 + 底部按钮区不重叠 |

**自检**：`node figma-plugin/verify-plugin.js` → **64/64 PASS / EXIT=0**（新增：**19/19 Screen 与 10/10 Overlay** 均"有子图层"、触发按钮落在源 Frame 内数量 = 0、决策便签不横向溢出、续帧数/内容/「源为 TabBar 页的续帧含 TabBar 实例」、无 `UI 绘制失败` 日志；Screen/Overlay/连接数断言已全部改为随 `SPEC` 动态取值，避免硬编码漂移）。


**诚实边界（未做，勿声称）**：
- 坐标为逐屏重排的**中高保真**，非像素级还原；未与浏览器截图做逐像素比对（本环境无法查看画布，只能靠用户截图迭代）。
- D2/D6/D7/D8 仍为**黄色"决策占位"**便签，D1/D3/D4/D5/D9 为**绿色"已确认"**；待开发 API 一律灰置 `disabled:` 占位。
- 尚未做 Phase 4 回读校验（`get_figma_data`）与像素级视觉回归。

### 7.3 真实基准对齐（2026-10-18 第三轮）

**触发**：用户第三次反馈"学员小程序页面产生的原型，与实际已经开发的界面不匹配"，并附 Figma 画布截图。

**根因**：插件此前以「独立 HTML 原型 v8」为视觉基准，而用户期望的是 `apps/miniapp` **真实已开发界面**。经 `AskUserQuestion` 收敛，用户明确选择：**「已开发页用真实 `apps/miniapp`、未开发页用 HTML 原型」+「先修结构性不一致」**。

**实测差异（真实源码 vs 插件对齐前）**：

| 项 | 真实（`apps/miniapp`） | 插件（对齐前） |
|---|---|---|
| 底部导航 | **3 Tab**：首页 / 排期 / 我的（`HomeTabBar.vue` / `StudentTabBar.vue`），选中 `#8b7355` / 未选中 `#999`，图标 48rpx、label 22rpx、indicator 40×4rpx 渐变 `#c9a66b→#d9a7b0` | 4 Tab（含「AI助手」），选中 `#C9A66B` |
| AI 助手 | 悬浮入口组件 `AiAssistant.vue`（`ai-fab` 圆形按钮 + unread 徽章 + 「AI助手」文案），**已接入 `POST /api/v1/ai/chat`** | 一级 Tab 整页，标注"模拟对话（未接入真实 AI）"（**事实错误**） |
| 首页 | `courses/index.vue`：AppNavbar 地点选择 + Banner swiper + 师资横滑 + 推荐课程 + 舞蹈视频 | 结构近似，缺 AI 悬浮入口 |
| 我的 | `profile/index.vue`：菜单行 = **图标 + 标题 + 描述 + 右箭头**（预约记录 / 解绑微信 / 退出登录） | 无图标、描述文案不符、退出登录画成独立按钮 |
| 我的会员卡 | `membership/index.vue`：原生导航栏「我的会员卡」+ filter-tabs + 卡片含**复制卡号按钮** / 「立即激活」/「预计解冻 + 提前解冻」 | 无导航栏、无复制按钮 |
| 预约记录 | `bookings/index.vue`：AppNavbar 标题 **「预约记录」** | 仅「‹ 返回」无标题 |
| 预约确认 | `booking-confirm/index.vue`：AppNavbar 标题 **「预约确认」** | 无导航栏 |
| 排期 | `schedule/index.vue`：AppNavbar「排期列表」+ 日期栏**从「今日」起** | 日期栏含「昨天」 |

**冲突记录（Reconciliation，不静默选择）**：

- **Conflict**：`project_memory` 硬约束「学员端小程序原型的底部导航必须固定为四个同级入口：首页、排期、AI助手、我的，**不得将 AI 助手设计为悬浮按钮/弹窗/抽屉/内嵌窗口**」 **与** 已开发真实代码（3 Tab + `AiAssistant.vue` 悬浮 FAB）直接冲突。
- **Evidence**：`apps/miniapp/src/components/HomeTabBar.vue`（3 `tab-item`：首页/排期/我的）、`StudentTabBar.vue`（同）、`AiAssistant.vue`（`ai-fab` 悬浮 + `ai-chat-window` 弹窗）、`pages.json` 学员页清单中**无 AI 页**。
- **Impact**：若继续按 4 Tab + AI 一级页绘制，则原型与真实界面持续不匹配，且会把"已接入真实 AI"误标为"模拟对话"。
- **Recommendation**：**以真实已开发代码为准**（用户已选"已开发页用真实"）；即 TabBar 降为 3 Tab，AI 助手以 `AiFab` 悬浮组件实例挂到 P-M8/P-M3/P-M9/P-M6/P-M4；`project_memory` 该条硬约束视为**过时**，需修订，AI 页 P-M10/P-M10b 降级为"规划态整页展示"（帧内 `ProtoNote` 显式声明与真实结构不一致）。

**本轮落地（`code.js`）**：

1. `SPEC.tabbar` 4 → 3 项（含 `glyph` / `route` / `realSource`），新增 `SPEC.aiFab`（56×70）与 `attachPages`；`SPEC.tabBarPages` → 3 真实页 + P-M10/P-M10b = `'none'`。
2. `createTabBar` 重写：图标 22×22 圆角方块 + 首字 glyph、label 11px、边框 `#f5f5f5`、indicator 20×2 `@ y=h-2`、`activeKey='none'` 全不选中。
3. 新增 `createAiFab()`：52px **紫色圆（`#667eea`）** + `AI` 字 + 16px 红点徽章 + 「AI助手」文案；`addAiFabs()` 挂到 5 个页 + P-M8b。
4. `UI` 新增 `M`（学员小程序真实主题令牌，来源 `styles/theme/_variables.scss`）；`UI.C.goldBg` → `#FAF8F5`。
5. `drawPM10` / `drawPM10b` 对齐真实 `AiAssistant.vue`：header 「AI 助手 / 智能课程助手」+ 紫色 AI 图标 + 清空；快捷卡 = 真实 `quickActions` 4 组（label + description）；错误气泡文案改为真实的「网络错误，请检查连接后重试」；删除"模拟对话/绿点"等失实标注。
6. `drawMiniCardItem` 补**复制卡号按钮**（双矩形矢量，避免缺字）。
7. `drawPM9` 重构为真实菜单行结构（图标 + 标题 + 描述 + 右箭头）；新增 `drawMenuRow()`。
8. P-M1 / P-M1c / P-M1d / P-M4 / P-M6 / P-M6b 改用 `drawMobileShell` 原生导航栏（「我的会员卡」/「预约确认」/「预约记录」）；P-M3 日期栏改为「今日」起。
9. 连线：`P-M8 > TabBar 项` 目标 `P-M8/P-M3/P-M9`（去掉 P-M10）；新增 `P-M8 > AI 悬浮入口` 灰置占位。
10. `frames.json` 补 `figma_representation_notes.real_alignment`（含 `real_source_map` 与 `developed_flag`）及每帧 `real_source` / `developed` / `aligned_against_real` 字段。

**自检**：`node figma-plugin/verify-plugin.js` → **64/64 PASS / EXIT=0**（TabBar 变体仍 4 个：home/schedule/profile/none；单组件由 1 → 2：`BookingListItem` + `AiFab`；顶层组件 10 → 11）。

**尚存未对齐（下一轮）**：
- 学员小程序帧的文字/状态色仍主要用 `UI.C`（Element Plus 口径）；真实主题令牌 `UI.M` 本轮仅迁移了背景与 AI 色、TabBar 色。
- P-M1 未画真实 `membership/index.vue` 的「无法激活的卡」分支（`getActivationBlockReason` 非空时仅显示使用信息、无激活按钮）。
- P-M4 未画真实 `booking-confirm/index.vue` 的 `OV-CARDSEL` 与「注意事项卡」逐条对齐核验（结构已有，文案未逐字核对）。

### 7.4 基准回归 HTML 原型 + 学员端完整性补全（2026-10-18 第四轮）

**触发**：用户第四次反馈"Figma 中画的原型，需要和浏览器中查看的原型一致，目前完全回去贴合实际的页面了，且小程序的页面几乎都不完善，请补充完整，需要完全完整"。

**决策（用户经 `AskUserQuestion` 确认）**：学员小程序页以浏览器 HTML 原型 `prototype/index.html` 为**唯一视觉基准**；本轮**撤回第三轮**"对齐真实 `apps/miniapp`"口径（含 3 Tab、`AiFab` 悬浮、P-M3 今日起、P-M10 规划态等）。

**冲突记录（Reconciliation，不静默反转）**：

- **Conflict**：第三轮结论（基准=真实代码 → 3 Tab + AI 悬浮）与第四轮用户指令（基准=HTML 原型 → 4 Tab + AI 一级 Tab）**直接相反**。
- **Evidence**：`prototype/index.html` `TAB_DEFS`(L1284) = 4 Tab（首页/排期/AI助手/我的）、`TAB_PAGES`(L1285)、`stuM10()`(L1447) 为完整一级 AI 页；真实 `HomeTabBar.vue` 为 3 Tab + `AiAssistant.vue` 悬浮。
- **Impact**：两者不可同时满足；按用户第四轮指令交付以 HTML 原型为准，真实端差异**显式备案**而非抹除。
- **Recommendation**：**以 `prototype/index.html` 为准**（§7.3 的实测差异表保留，作为"与真实端的差异备案"）；`frames.json` 新增 `student_prototype_baseline`（含 `prototype_source_map` + `ai_entry` 差异备案）。

**本轮落地（`code.js` + 规格）**：

1. TabBar 回归 **4 Tab**（首页 / 排期 / AI 助手 / 我的，`active=ai` 用于 P-M10/P-M10b）；**移除 `AiFab`** 悬浮组件（原型无悬浮 FAB）。
2. P-M10 / P-M10b 回归原型 `stuM10`：副标题"智能课程助手 · 模拟对话（未接入真实 AI）"、欢迎"您可以问我："、4 张常用问题卡、固定输入区；删除"规划态 / 已接入 `/api/v1/ai/chat`"措辞。
3. P-M3 日期栏回归原型 `stuDateList()`（i=-1..+3）：昨天 / 今日 / 明日 / 周X / 周X，选中今日。
4. **P-M4 补 `OV-CARDSEL`**（原型 `card-selector-popup`）：标题「选择会员卡」+ 单选点 + 卡名 + 剩余/有效期 + 不可用原因 + 卡号 + 类型徽标 + 底部「确定」；登记进 `SPEC.overlayFrames` 与连线。
5. **学员端图标全部改真实 SVG 矢量**：新增 `TAB_ICONS` / `AI_ICONS` / `MISC_ICONS`，经 `figma.createNodeFromSvg`（`uiIconSvg` / `uiIconChip`）渲染，替换原单字方块占位（`课/卡/注/室/人/…`）。
6. 逐帧核对 index.html 全部元素（P-M1 / P-M1c / P-M1d / P-M2 / P-M3 / P-M4 / P-M5 / P-M5b / P-M6 / P-M6b / P-M8 / P-M9 / P-M10 / P-M10b）。
7. 规格同步：`frames.json`（`student_prototype_baseline`、`prototype_source`、`prototype_aligned`）、`components.json`（TabBar 4 Tab、删 `AiFab`）、`interactions.json`（补 `OV-CARDSEL` 连线、TabBar 4 Tab 备注）。

**自检**：`node figma-plugin/verify-plugin.js` → **64/64 PASS / EXIT=0**（Page=3、Screen=19、Overlay=10、单组件 1、顶层组件 10、reaction=40、灰置=11）。

**渐变填充补齐（2026-10-18 追加）**：

用户要求"先处理渐变填充问题"。原插件把所有 CSS 渐变近似成纯色，本轮改为**原生 `GRADIENT_LINEAR` 填充**：

- 新增 `gradStop` / `cssLinearGradient`（CSS 角度 → Figma `gradientTransform`）/ `fillPaints`（纯色 | 渐变 | 多填充派发）三个工具函数，并集中登记 `GRAD` 渐变常量表（严格取自 `prototype/index.html` 的 `linear-gradient`）。
- 三个共享基元 `uiPanel` / `uiRect` / `uiCircle` 统一改走 `fillPaints`（`makeText` 仍为纯色，不做渐变文字）。
- 已转换的调用点覆盖学员端全部页面（金按钮 `goldBtn`/`goldBtnSoft`、金卡 `goldCard`/`cardGrey`/`cardFrozenBg`/`cardVoidBg`、`avatarGold`、`memCard`/`memIc`/`menuIc`/`logoutIc`/`memberBadge`、`card3d`、`bannerBg`/`bannerOverlay`、`teacherAvatar`/`courseImage`/`videoCover`/`videoOverlay`、`timeSection`/`timeDivider`/`tagRegular`、`headerLine`、`pageBg`/`profileBg`、TabBar 下划线 `tabIndicator`），以及管理端 `adminBtn`、教师端 `tchHead`/`tchBody`。
- 自检 `node verify-plugin.js` 仍 **64/64 PASS / EXIT=0**（纯填充改动，未改变任何节点/连线/便签计数）。

**尚存未对齐（下一轮，需在 Figma 内重跑后校准）**：

- 未做像素级视觉回归（渐变角度/停靠点按 CSS 换算，需在 Figma 内目视比对微调）。
- Phase 4 回读校验（`get_figma_data`）未做（本环境无 Figma 写权限，且需用户重跑插件后画布才有内容）。

### 7.5 根因定位与修复：Figma 实际输出「太简陋 / 大片空白」（2026-10-18 第六轮）

**触发**：用户第六次反馈"生成的 HTML 页面在浏览器端是上图中的四个页面、而原型页面太简陋了、不完善、没有根据前四个图来绘制（如第五个图），是怎么回事、该怎么解决"。

**根因（已验证，非猜测）**：`code.js` 的 `hexToRgb` 只支持 6 位十六进制，**无法解析 `rgba(...)` 与 `transparent`** → 产生 `NaN` 颜色通道 → 真实 Figma 在写入 `fills` / `strokes` 时会校验并**抛错**，异常沿调用栈冒泡到 `paint()` 的 `try/catch` → 该帧 `drawScreen` **中途中断**，只剩中断前已画的元素（表现为"只有标题、其余大片空白"）。

- **Evidence（实测）**：旧解析器对 `rgba(201,166,107,.14)` 得 `{r:NaN, g:0.729, b:NaN}`；新校验器对该值抛 `Invalid paint color channel (NaN)`（即真机行为）。
- **Evidence（与截图吻合）**：P-M10 在 header 之后的**第一句**即为 `fill:'rgba(201,166,107,.14)'`（欢迎徽标）→ 徽标 + 4 张常用问题卡 + 输入区全部未画（截图=P-M10 仅 header + 空白）；P-M8 推荐课程卡的 `stroke:'rgba(201,166,107,.12)'` → 课程/视频卡缺失；P-M1 卡内分隔线 `fill:'rgba(201,166,107,.28)'` → 首张卡后截断。全库共约 10 处 `fill`/`bg` 与 13 处 `stroke` 使用 `rgba()`，另有 `border:'transparent'`。
- **为何自检 64/64 仍 PASS**：`verify-plugin.js` 的桩把 `fills`/`strokes` 当作**普通属性赋值**，永远不会校验、也永远不抛错 → 计数全过，但真机渲染是残帧。这就是"计数对了 ≠ 视觉对了"。

**本轮修复**：

1. `hexToRgb` 支持 `#rgb` / `#rgba` / `#rrggbb` / `#rrggbbaa` / `rgb()` / `rgba()` / `transparent`，返回 `{r,g,b,a}` 并带 NaN 兜底；`solid()` 支持 alpha（`p.opacity = a × 入参 opacity`）；`gradStop()` 支持 alpha。变量路径 `setValueForMode` 也随之为合法的 `{r,g,b,a}`。
2. `verify-plugin.js` 的桩对 `fills` / `strokes` 写入做**与 Figma 一致的校验**（颜色含 NaN 即抛错）→ 该类"静默残帧"问题今后**无法假通过**，会被既有断言「无 UI 绘制失败日志」捕获。

**自检**：`node figma-plugin/verify-plugin.js` → **64/64 PASS / EXIT=0**；`node --check code.js` → SYNTAX_OK。

**尚存（下一轮）**：

- `hexToRgb` 现对任意非法格式**静默兜底为 0**（不再抛错），属"更安全但不报错"；如需严格，可另加颜色格式白名单断言。
- 仍需用户在 Figma 桌面端**重新导入运行插件**后回传截图，做像素级视觉回归（渐变角度/停靠点）与 Phase 4 回读校验。

---

## 8. 失败回退方案

| 失败点 | 回退动作 |
|---|---|
| **Page 计划上限（Starter = 3 页）** | **已实施**：改为紧凑模式（复用既有 Page + 清空重建，不足才新建），11 组归并 3 组，见 §7.1 |
| 插件运行报错 / 部分节点未建 | 降级为**分阶段运行**：先只建 Variables+Styles，再建 Components，再建 Frames；每步单独校验 |
| Variables 因计划受限无法创建 | 退化为 **Color/Text/Effect Styles**（非 Variables），在文档标注此差异 |
| reaction / 连线 API 不可用 | 退化为**仅画静态连线（箭头 + 标签）**，在交付说明中标注"Prototype 连线未生效" |
| 无法获得 Figma 编辑授权 | **暂停 Phase 3+**，仅交付 Phase 0–2（规格 + 插件代码），明确列为阻塞 |
| 方案 B 完全不可行 | 降级**方案 A**（html.to.design）仅产出**视觉参考稿**，明确标注"无语义组件/Variables/连线，非验收交付物"，另行排期补 B |
| 回读校验发现偏差 | 修正 `figma-spec/*.json` → 重新生成插件 → 在 Figma 撤销上一次运行结果后重跑 |

> 所有回退均**不改动** `apps/` 业务代码与业务规则；原型 `index.html` 保持 v8 现状。

---

## 9. 需要人工确认的问题

1. **Figma 账号与目标 File**：~~需新建一个空 File 并提供 `fileKey`~~ → **已提供** `fileKey = Ovr4Zo8vPTohgqv9AZqIVr`。
2. **付费计划**：~~账号计划是否支持 Variables？~~ → **已确认**为 Starter（免费）计划 → 不提供 Variables、Page 上限 3；插件已按**紧凑模式 + Styles 降级**适配。
3. **运行方式**：是否可在本机以 dev 插件方式导入运行 `figma-plugin/`？（**仍阻塞 Phase 3 的实际产出**；需先清理文件内 3 个空 Page 并重跑）
4. **规格口径确认**：是否同意按第 2 节**修订** `figma-creation-guide.md`（Frame 数由"15"改为"14 页面+9 弹窗"并纳入 P-M8/M9/M10）？
5. **决策便签口径确认**：是否同意"**D1/D3/D4/D5/D9 画成确定性交互 + 绿色已确认便签；D2/D6/D7/D8 保留黄色占位**"这一新版红线（覆盖旧指南的"一律黄色"）？
6. **范围确认**：AI 助手页（P-M10）为原型**有意超出真实端**的四 Tab 设计，是否纳入 Figma 交付？（真实 `HomeTabBar.vue` 仍为三 Tab）
7. **是否需要**方案 A 的 html.to.design 视觉 bootstrap？如需，请提供插件授权。
8. **交付边界**：是否仅交付 Figma 原型文件（不改 `apps/` 业务代码）？

---

## 附录 A：本报告的证据来源（可复核）

- 原型结构：`prototype/index.html`（`<script>` L582、`STATE` L666、`renderAdminPage` L855–865、`renderStuPage` L1303–1321、`renderTeacher` L1905；`.sticky` L117、`.cnote` L160、`.desc-grid` L145–150、`.card-status-badge` L106）。
- 页面/弹窗函数名：`adminA1/adminA2/adminA5/adminA6`、`stuM1–M10`、`openIssueModal/openCardDetail/openProductModal/openBatchDeleteProducts/openBatchCancelCards/openFreezeModal/openRenewalModal/openConflictModal/openCancelModal`。
- 规格：`figma-creation-guide.md`（11 Page、组件 2.1–2.10、Frame 3.1–3.14、连线第 4 节、流程第 5 节、Token 第 6 节、D9 第 7 节）、`screen-inventory.md`、`interaction-spec.md`、`prototype-acceptance.md`（AC1–AC10 + 五红线）。
- 决策：`open-decisions.md`（L116–124：D1/D3/D4/D5/D9 已于 2026-10-16 确认；D2/D6/D7/D8 待确认）。
- 验证：`verify-prototype.js` 实跑 `PASS 121 / FAIL 0 / EXIT=0`。
- 环境：`~/.trae-cn/mcps/s_class_booking_system-efb09230/browser_use/mcp_Figma_AI_Bridge/`（仅 `get_figma_data`、`download_figma_images`）；`FIGMA_*` 环境变量为空；无 Figma CLI / 桌面 App / npm 包。

## 附录 B：本次未做（严格约束遵守）

- 未修改任何 `apps/` 业务代码；未改动会员卡业务规则。
- 未将 D2/D6/D7/D8 画成确定交互；未将待开发 API 设计为可用。
- **未创建**任何 Figma 文件/组件/连线（因缺授权与工具，已列为阻塞项）。
- 未改动 `prototype/index.html`（保持 v8）。
