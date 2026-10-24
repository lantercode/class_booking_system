# F3.1 — miniapp 运行时崩溃修复 · 实施方案

> Feature ID：F3.1
> 作者：project-architect
> 日期：2026-09-24
> 性质：纯 import 补全，不改动任何业务逻辑 / API / 数据库 / UI
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`

---

## Root Cause

### 崩溃点 1：`pages/teacher/schedule/index.vue:190`

- 调用链：`onMounted`（L162-174）→ `checkLogin('teacher')` 通过 → `loadSchedules()`（L173）→ `await teacherApi.getSchedules(...)`（L182）→ L190 `schedules.value = extractList(result)`。
- 原因：文件 import 区（L104-111）引入了 `teacherApi / scheduleApi / checkLogin / formatDateTime / navigateTo` 等，唯独没有 `extractList`。uni build（esbuild 转换、不做类型检查，rollup 对未定义标识符仅警告不报错）无法拦截，符号以自由变量形式进入产物，运行时求值抛出 `ReferenceError: extractList is not defined`。
- 实际症状（以真实代码为准，详见 ## Conflict）：该 ReferenceError 发生在 `loadSchedules` 的 try 块内（L181-193），被既有 `catch` 吞掉并 toast「加载失败」，页面渲染为空网格——表现为"功能不可用"，而非整页白屏崩溃。

### 崩溃点 2：`pages/teacher/students/index.vue:134 / :153`

- 调用链：`onMounted`（L108-120）→ `loadSchedules()` → L134 `scheduleList.value = extractList(result)`（解析今日进行中排期）；若有排期 → `loadStudents()`（L137）→ L153 `students.value = extractList(result)`（解析预约名单）。
- 原因：import 区（L88-94）无 `extractList`。两处缺的是**同一个符号**，一次 import 同时修复；L153 位于 `loadStudents`，只有 L134 先成功才会执行到——与 user-flow §2.3 描述一致。
- 症状同崩溃点 1：异常被各自 try/catch 吞掉 → toast「加载失败」+ 空列表。

### 崩溃点 3：`pages/student/schedule/index.vue:570`

- 调用链：`onMounted`（L557-591）→ `checkLogin('student')` 通过 → L569-581 的 try 块 → L570 `await tenantApi.getSettings()`。
- 原因：import 区 L147 `import { bookingApi, courseTypeApi, membershipApi, scheduleApi } from "@/api"` 缺少 `tenantApi`（该文件 extractList 已在 L159 正确导入）。
- 实际症状（关键核验结论）：L570 在 try 块内，ReferenceError 会被 L579-581 的 catch 捕获，走"租户配置失败降级"分支（`console.warn` + 默认 90 分钟）；L585-588 的 `loadCourseTypes/loadSchedules/loadBookings/loadMembershipCards` 在 try 块**之外**，仍会执行。**页面不会整体崩溃，但租户配置永远静默降级为默认值**——这与 user-flow §3.3"后续全部不执行"的描述不一致，详见 ## Conflict。

### 为什么运行时才触发

miniapp 构建链路（`uni build -p mp-weixin`）不经 `vue-tsc` 类型检查（类型门禁属 F3.2），未导入符号在构建期不产生错误，直接流入小程序运行时。

### 为什么补 import 即可解决

两个符号均已存在且行为兼容：`extractList`（`src/utils/helpers.ts:29`，兼容数组 / `data.items` / `data.list` 等信封形态，兜底返回 `[]`）；`tenantApi`（`src/api/index.ts:538`，含 `getSettings`）。调用点的实参形态与实现预期一致，无需任何适配代码。

---

## Affected Files

### 1. `apps/miniapp/src/pages/teacher/schedule/index.vue`

现状 import 区（L104-111，单引号、无分号风格）：

```ts
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { teacherApi, scheduleApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import { formatDateTime } from '@/utils/date'
import TeacherTabBar from '@/components/TeacherTabBar.vue'
import AiAssistant from '@/components/AiAssistant.vue'
import { navigateTo } from '@/utils/navigation'
```

崩溃行（L190）：

```ts
    schedules.value = extractList(result)
```

全文符号核对：`teacherApi`（L182）、`scheduleApi`（L237）、`checkLogin`（L163）、`formatDateTime`（L78）、`navigateTo`（L256/261/265/269/273）均已导入；`extractList` 仅 L190 一处使用，是唯一缺失符号。

### 2. `apps/miniapp/src/pages/teacher/students/index.vue`

现状 import 区（L87-94，单引号、无分号风格）：

```ts
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { teacherApi, bookingApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import { formatDate, formatTime } from '@/utils/date'
import TeacherTabBar from '@/components/TeacherTabBar.vue'
import AiAssistant from '@/components/AiAssistant.vue'
import { navigateTo } from '@/utils/navigation'
```

崩溃行（L134、L153）：

```ts
    scheduleList.value = extractList(result)
    ...
    students.value = extractList(result)
```

全文符号核对：`extractList` 有且仅有 L134/L153 两处（grep 确认无第三处）；`teacherApi`、`bookingApi`（L148/190）、`checkLogin`、`formatDate/formatTime`、`navigateTo` 均已导入。

### 3. `apps/miniapp/src/pages/student/schedule/index.vue`

现状 import 区（L146-160，双引号、带分号风格）：

```ts
<script setup lang="ts">
import { bookingApi, courseTypeApi, membershipApi, scheduleApi } from "@/api";
import AiAssistant from "@/components/AiAssistant.vue";
...
import { extractList } from "@/utils/helpers";
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
```

崩溃行（L570）：

```ts
    const settingsResult = await tenantApi.getSettings();
```

全文符号核对：`tenantApi` 仅 L570 一处使用，未导入；`bookingApi / courseTypeApi / membershipApi / scheduleApi / checkLogin / extractList`（L159 已导入）及其余符号均已导入。

---

## Exact Fix

仅 3 个文件各加 1 行（或改 1 行），风格与各文件现有 import 保持一致：

| # | 文件 | 改动 | 插入位置 |
|---|------|------|---------|
| 1 | `apps/miniapp/src/pages/teacher/schedule/index.vue` | 新增 `import { extractList } from '@/utils/helpers'` | L108（`formatDateTime` 行）之后，与其他 `@/utils/*` import 相邻；单引号、无分号 |
| 2 | `apps/miniapp/src/pages/teacher/students/index.vue` | 新增 `import { extractList } from '@/utils/helpers'` | L91（`formatDate, formatTime` 行）之后；单引号、无分号 |
| 3 | `apps/miniapp/src/pages/student/schedule/index.vue` | 将 L147 改为 `import { bookingApi, courseTypeApi, membershipApi, scheduleApi, tenantApi } from "@/api";` | 原行内追加 `tenantApi`（按字母序置于末尾）；双引号、带分号 |

禁止任何其他改动（含格式化整文件、顺手修复其他问题）。

---

## Why Import Fix Is Sufficient

1. 符号实现已存在且被其他页面生产使用：`extractList` 已被 6 个页面以同款方式导入使用（`teacher/courses/index.vue:101`、`teacher/schedule/form.vue:121`、`student/courses/index.vue:217`、`student/courses/list.vue:65`、`student/courses/detail.vue:153`、`student/schedule/index.vue:159`）；`tenantApi` 已被 `student/courses/index.vue:210`、`student/bookings/index.vue:120`、`student/booking-confirm/index.vue:239` 正常导入使用。
2. 调用实参与实现兼容：3 处 `extractList(result)` 的 `result` 均为小程序请求层返回的 `{code,msg,data}` 信封，`extractList` 对数组 / `items` / `list` / 嵌套 `data` 均有兜底；`tenantApi.getSettings()` 无参调用与 `api/index.ts:538` 的导出一敛。
3. 错误均被既有 try/catch 覆盖，补 import 后执行路径不变，只是不再抛 ReferenceError，无逻辑分叉风险。

---

## Dependency Analysis

### 被引用符号导出证据

- `extractList`：`apps/miniapp/src/utils/helpers.ts:29` `export function extractList<T = any>(...)`，已读取全文确认实现完整。
- `tenantApi`：`apps/miniapp/src/api/index.ts:538` `export const tenantApi = {`（grep 导出清单确认，同文件含全部 14 个 api 导出）。

### Alias 配置

- `apps/miniapp/tsconfig.json` 已配置 `paths: { "@/*": ["./src/*"] }`（vue-tsc 可解析）。
- `apps/miniapp/vite.config.ts` 未显式声明 alias，`@ → src` 由 `@dcloudio/vite-plugin-uni` 内置提供；现存大量同款 `@/api`、`@/utils/*` 导入（含本 Feature 3 个文件自身的其他 import）即为可解析证据。

### 其他引用方影响

- `extractList` 全库引用 9 个文件（含 helpers.ts 自身）：除 2 个待修页面外其余均已正确导入。
- `tenantApi` 全库引用 5 个文件：除 `student/schedule/index.vue` 外均已正确导入（booking-confirm 已核实 L239 导入，排除第 4 个崩溃点）。
- 本次只新增 import，不改 `helpers.ts` / `api/index.ts` 及任何共享模块，对其他页面零影响。

### 外部依赖

无后端、数据库、契约、密钥、环境变量变更。

---

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 页面此前数据加载从未成功过，补 import 后可能暴露下一层运行时问题（数据结构不匹配、渲染异常） | 中 | 验收按 AC-3/4/5 走完整主流程；新发现问题记录为独立缺陷，不在本 Feature 顺手修 |
| import 风格与文件不一致（引号/分号）引发 lint 噪音 | 低 | 按 Exact Fix 表执行，逐文件对齐现有风格 |
| 修复范围被扩大 | 低 | `git diff --stat` 必须恰好 3 个文件、每文件 diff 仅 1 行（AC-1.4/1.5） |

---

## Required Agents

| Agent | 是否需要 | 依据 |
|-------|---------|------|
| **frontend-engineer** | ✅ 需要 | 改动全部落在 `apps/miniapp`（uni-app 前端），属 v3 责任矩阵中 frontend 专属域（uni-app / 页面 / 构建自验 R8） |
| backend-engineer | ❌ 不需要 | 无后端代码、无 OpenAPI 契约变更；消费的端点（`teacherApi.getSchedules`、`bookingApi.list`、`tenantApi.getSettings`）均已存在 |
| database-engineer | ❌ 不需要 | 无 Migration / 索引 / 约束变更，不触数据层 |
| mcp-engineer | ❌ 不需要 | 不涉及 `POST /api/v1/ai/chat` 契约与任何 Tool；页面内 `AiAssistant` 组件本次不改动 |

Agent Selection 结论（v3 §1）：单端纯前端修复，仅召 frontend-engineer；test-engineer 未配置，按 §6.4 由 frontend 自验 + Architect 抽检（人工冒烟）。

### Frontend Handoff Package（摘要）

1. 受影响 App 矩阵：仅 `[x] miniapp`
2. 变更清单：修改 3 个既有页面文件（见 Exact Fix），无新建、无路由变更
3. API 契约：无变更，全部为既有端点消费
4. 鉴权：无变更（`checkLogin` 页面级校验、请求层 401 refresh 均为既有）
5. AI UI 专项：不涉及（Gate 不触发）
6. Pinia / 缓存影响：无
7. 多端差异：无（仅 mp-weixin 单端）
8. 冒烟用例：见 Verification Plan

---

## Implementation Steps

1. **修改前快照**：在 `apps/miniapp` 执行 `npx vue-tsc --noEmit 2>&1 | wc -l`（或保存完整输出），记录 TS 错误基线。验证方式：输出留档。
2. **改文件 1**：`pages/teacher/schedule/index.vue` 插入 `import { extractList } from '@/utils/helpers'`（L108 后）。验证：grep 确认 import 存在且仅 1 处新增。
3. **改文件 2**：`pages/teacher/students/index.vue` 同样插入（L91 后）。验证：同上。
4. **改文件 3**：`pages/student/schedule/index.vue` 在 L147 的 `@/api` 导入中追加 `tenantApi`。验证：同上。
5. **范围自检**：`git diff --stat` 恰好 3 个文件；`git diff` 逐行确认仅 import 变更。验证：AC-1.4/1.5。
6. **类型对比**：重跑 `npx vue-tsc --noEmit`，错误数 ≤ 基线（预期减少 3 处"找不到名称"类错误，清零属 F3.2）。验证：AC-2.3。
7. **构建**：`npm run build:mp-weixin`（package.json 已确认脚本名）。验证：exit code 0（AC-2.1），抽查 `dist/build/mp-weixin` 对应页面 js 中符号引用有效（AC-2.2）。
8. **运行时冒烟**：微信开发者工具按 AC-3/4/5 人工执行。

---

## Verification Plan

| AC 编号 | 验证方式 | 责任方 |
|---------|---------|--------|
| AC-1.1 ~ AC-1.3 | 查看 3 文件 import 区（对照 Exact Fix 表） | frontend 自验 + Architect 抽检 |
| AC-1.4 / AC-1.5 | `git diff` / `git diff --stat` | 同上 |
| AC-2.1 / AC-2.2 | `npm run build:mp-weixin` + 产物抽查 | frontend（R8 证据留档） |
| AC-2.3 | `vue-tsc` 修复前后错误数对比 | frontend |
| AC-3.x 教师排期页 | DevTools 人工：加载 / 周切换 / 空周 / 详情 / 断网 | 人工冒烟（Architect 组织） |
| AC-4.x 教师学员页 | DevTools 人工：今日排期默认选中 / 名单 / 切换 / 状态文案 / 两种空态 / 断网 | 同上 |
| AC-5.x 学员排期页 | DevTools 人工：四区域加载（AC-5.2）/ 租户配置生效（5.3）/ 降级（5.4）/ 预约跳转 / 无卡拦截 / 空态 / 断网 | 同上 |
| AC-6.x 权限 | 未登录 / 角色不匹配 / Token 过期三场景 × 3 页面 | 同上 |
| AC-7.x 健壮性 | 快速切页（isUnmounted）/ 异常响应兜底 | 同上 |

注意（与 ## Conflict 联动）：AC-5.2 的"修复前后对照"描述基于不准确的因果推断，执行口径应为：**修复后**四个区域均正常加载即 PASS；不要试图通过"修复前观察后三个区域不加载"来复现对照（实际修复前它们也会加载，详见 Conflict）。

---

## UNKNOWN

| # | 项 | 验证方法 |
|---|----|---------|
| U1 | 补 import 后 3 个页面首次真实跑通数据加载，是否暴露下一层运行时错误（如渲染字段缺失、`handleBookingSuccess` 等未逐行审计的下游逻辑） | AC-3/4/5 人工冒烟覆盖；发现问题登记独立缺陷，不扩大本 Feature |
| U2 | 当前 `vue-tsc` 基线错误数（requirement 提及"30+ TS 类型错误"，未逐一核实） | 实施 Step 1 留档基线输出 |
| U3 | AC-5.3（租户配置生效）依赖后端可改 `booking_cancel_minutes` 的测试环境 | 验收前与后端环境负责人确认可配置性 |

---

## Conflict

### Conflict 1：user-flow §3.3 "570 行崩溃阻断后续全部加载" 与真实代码不符

- **Conflict**：user-flow.md L107 称"修复前该 ReferenceError 直接打断 `onMounted`，导致后续 `loadCourseTypes / loadSchedules / loadBookings / loadMembershipCards` 全部不执行"；requirement.md 表格称学员"无法进入排期浏览页"；AC-5.2 备注沿用同一因果（"修复前 570 行崩溃会导致后三个区域不加载"）。
- **Evidence**：`student/schedule/index.vue` L569-581 的 try 块**只包裹** `tenantApi.getSettings()`；L585-588 的四个 load 调用在 try 之外。ReferenceError 属同步求值异常，会被 L579 `catch` 捕获（走 console.warn + 默认 90 分钟降级），后续 load **仍会执行**。
- **Impact**：修复方案不受影响（补 import 依然正确且充分）；真实影响面小于文档描述——学员页实际症状是"租户取消时限配置永远静默降级为默认 90 分钟"（且 warn 文案与网络失败无法区分），而非整页不可用。文档对严重程度的描述偏重，但修复优先级结论（P0）因"配置降级难以察觉、影响取消规则正确性"依然成立。
- **Recommendation**：以真实代码为准。本 plan 已按真实行为撰写；requirement.md / user-flow.md / acceptance.md 的对应措辞作为文档勘误另行小修（不在本 Feature 代码改动内），验收执行口径按 Verification Plan 中的说明执行。

### Conflict 2：requirement.md "页面加载即抛出 ReferenceError" 的崩溃定性

- **Conflict**：requirement.md L17 称 3 个页面"页面加载即抛出 ReferenceError"；实际 3 处异常均位于既有 try/catch 内（教师两页在 `loadSchedules/loadStudents` 的 try 中，学员页在租户配置 try 中），均为**被捕获**的异常。
- **Evidence**：teacher/schedule L181-193、teacher/students L127-141/L147-156、student/schedule L569-581。
- **Impact**：教师两页真实症状为 toast「加载失败」+ 页面空数据（控制台无红色未捕获异常，错误被空 catch 吞掉），而非白屏崩溃；修复必要性与方案不变。AC 中"控制台无 ReferenceError / 红色未捕获异常"的判定在修复前也可能因异常被吞而"假 PASS"，验收时应以**功能恢复**（数据正常渲染）为主判定，而非仅看控制台。
- **Recommendation**：同上，作为文档勘误记录；验收口径按上条执行。
