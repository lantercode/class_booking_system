# F3.1 — miniapp 运行时崩溃修复 · 实施报告

> Feature ID：F3.1
> 执行日期：2026-09-24
> 执行方式：主 Agent 直接执行（单领域最小修改，按 orchestration 规则无需调用 specialist）
> 约束遵守：仅 import 层最小修改，未改业务逻辑 / API / 数据库 / MCP / UI

---

## Changed Files

| # | 文件 | 变更 |
|---|------|------|
| 1 | `apps/miniapp/src/pages/teacher/schedule/index.vue` | +1 行 import |
| 2 | `apps/miniapp/src/pages/teacher/students/index.vue` | +1 行 import |
| 3 | `apps/miniapp/src/pages/student/schedule/index.vue` | 1 行 import 追加一个符号 |

未创建、未删除任何文件；未修改 `utils/helpers.ts`、`api/index.ts` 或任何其他文件。

## Exact Changes

### 1. teacher/schedule/index.vue（L109 新增）

```diff
 import { formatDateTime } from '@/utils/date'
+import { extractList } from '@/utils/helpers'
 import TeacherTabBar from '@/components/TeacherTabBar.vue'
```

修复点：L190 `schedules.value = extractList(result)`（原 P0-8）。

### 2. teacher/students/index.vue（L92 新增）

```diff
 import { formatDate, formatTime } from '@/utils/date'
+import { extractList } from '@/utils/helpers'
 import TeacherTabBar from '@/components/TeacherTabBar.vue'
```

修复点：L134 `scheduleList.value = extractList(result)` 与 L153 `students.value = extractList(result)`（原 P0-9，两处调用共用同一 import）。

### 3. student/schedule/index.vue（L148 修改）

```diff
-import { bookingApi, courseTypeApi, membershipApi, scheduleApi } from "@/api";
+import { bookingApi, courseTypeApi, membershipApi, scheduleApi, tenantApi } from "@/api";
```

修复点：L570 `await tenantApi.getSettings()`（原 P0-10）。该文件已有 `extractList` 导入（L160），无需重复添加。

插入位置均遵循文件既有 import 分组顺序与引号风格（教师两页单引号、学员页双引号）。

## Scope Verification

| 检查项 | 结果 |
|--------|------|
| 修改前 `git status` 确认无用户未提交修改被覆盖 | ⚠️ 见下方说明 |
| 本次变更文件数 | ✅ 3 个，与 requirement.md Scope 完全一致 |
| 每个文件 diff 仅含预期 import 修改 | ✅ 教师两页各 +1 行；学员页 L148 单符号追加 |
| 无业务逻辑 / 模板 / 样式 / 格式改动 | ✅ 本次编辑未触碰 import 区以外的任何行 |

**重要说明（非本次引入）**：`student/schedule/index.vue` 在修改**之前**就已是 git modified 状态（`validateCardForSchedule` 约 369-444 行的预存未提交改动）。本次仅在其 import 区 L148 追加 `tenantApi` 一个符号，未触碰那些预存改动。验收 AC-1.4「除 import 外无业务逻辑改动」针对的是**本次 Feature 的 diff**，预存改动不属本 Feature 责任范围，需用户知悉。

## Tests Run

| # | 检查 | 命令 | 结果 |
|---|------|------|------|
| 1 | mp-weixin 构建 | `npm run build:mp-weixin` | ✅ `DONE Build complete.` |
| 2 | 类型检查错误数 | `npx vue-tsc --noEmit` | 27 个错误（修复前 30+），**未增加反而减少** |
| 3 | extractList/tenantApi 相关错误 | `grep -iE "extractList\|tenantApi"` | ✅ NONE，全部消除 |

vue-tsc 剩余 27 个错误的文件分布：`teacher/schedule/form.vue`(6)、`student/bookings`(5)、`student/schedule`(4)、`booking-confirm`(3)、`AiAssistant`(3)、`student/courses`(2)、`api/index.ts`(2)、`teacher/profile`(1)、`courses/detail`(1)。全部为历史遗留，清零属 F3.2 Scope。

其中 `student/schedule/index.vue` 剩余 4 个错误（L197 `statusBarHeight` 可能 undefined、L396/406 `reasonType` 字面量类型不匹配、L572 `booking_cancel_minutes` 类型）均位于与本次修改无关的代码行，且 L396/406 源自上文提到的预存改动。

## Results

| 验收项（映射 acceptance.md） | 状态 |
|------------------------------|------|
| AC-1.1 / AC-1.2 / AC-1.3 三个 import 已补充 | ✅ PASS |
| AC-1.5 未改动 helpers.ts / api/index.ts / 其他文件 | ✅ PASS |
| AC-2.1 `uni build -p mp-weixin` 构建成功 | ✅ PASS |
| AC-2.3 TS 错误数不增加 | ✅ PASS（30+ → 27） |
| AC-1.4 diff 仅含 import 修改 | ✅ 本次编辑 PASS（学员页存在预存改动，见 Scope Verification 说明） |
| AC-3 ~ AC-7 运行时验证（微信开发者工具） | ⏸ 待人工执行（需真实后端 + 教师/学员账号） |

## Risks

| 风险 | 状态 |
|------|------|
| 页面此前未真正运行，可能暴露下一层运行时问题 | 仍存在，待 AC-3~AC-7 人工冒烟确认；按 Scope 约定，发现的新问题记录为独立缺陷，不在本 Feature 修复 |
| `student/schedule/index.vue` 携带预存未提交改动 | 已在报告中显式标注；提交时建议用户确认这些改动归属 |
| IDE 诊断曾提示教师两页存在未使用的 `goToXxx` 声明 | 预存问题（疑似 TabBar 导航残留），与本次无关，未处理 |

## UNKNOWN

| # | 未知项 | 验证方法 |
|---|--------|---------|
| U1 | 3 个页面在真实微信开发者工具中的运行时表现（数据渲染、空态、断网降级） | 按 acceptance.md AC-3~AC-7 人工执行 |
| U2 | `tenantApi.getSettings()` 返回类型为 `{}` 导致 L572 类型报错，运行时 `.data?.booking_cancel_minutes` 实际取值是否正确 | AC-5.3 人工验证（后端改配置后观察） |
| U3 | `student/schedule/index.vue` 预存改动（validateCardForSchedule）的归属与意图 | 询问用户是否为其他未完成工作 |

## Handoff

- **状态**：代码修改完成，静态验证（构建 + 类型 + diff 范围）全部通过。
- **下一步**：在微信开发者工具中按 `acceptance.md` AC-3 ~ AC-7 执行人工运行时验收（需要可连通的后端环境与教师/学员测试账号）。
- **验收注意**：AC-5.2 的判断口径以 implementation-plan.md 中修正后的描述为准（570 行原崩溃位于 try 内，真实症状是租户配置静默降级为默认 90 分钟，而非阻断后续 load）。
- **不在本次交付内**：F3.2（类型门禁 + 27 个存量 TS 错误清零）、F3.4（四态）、学员页预存改动的处置。
- **建议**：人工验收 PASS 后，由用户决定提交策略（注意将学员页预存改动与本次 import 修复区分提交，或先确认预存改动归属）。
