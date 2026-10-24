# F3.1 — miniapp 运行时崩溃修复 · 需求文档

> Feature ID：F3.1
> 来源：`docs/delivery/feature-backlog.md` Epic 3 / Feature 3.1；`docs/delivery/product-gap-analysis.md` P0-8 / P0-9 / P0-10
> 阶段：Phase 1（核心业务可交付）
> 状态：已定义，待开发
> 生成日期：2026-09-24

---

## 1. Goal

修复小程序 3 个页面因缺失 import 导致的运行时崩溃（ReferenceError），使教师排期、教师学员、学员排期页面能够正常加载并完成其核心业务操作。

## 2. Problem

`apps/miniapp` 有 3 个页面在 `onMounted` 数据加载阶段引用了未导入的符号，页面加载即抛出 ReferenceError，用户无法使用：

| 页面 | 崩溃位置 | 缺失符号 | 影响 |
|------|---------|---------|------|
| `pages/teacher/schedule/index.vue` | 第 190 行 `schedules.value = extractList(result)` | `extractList` | 教师无法查看自己的周排期 |
| `pages/teacher/students/index.vue` | 第 134 行、第 153 行 `extractList(result)` | `extractList` | 教师无法查看排期下的学员名单 |
| `pages/student/schedule/index.vue` | 第 570 行 `await tenantApi.getSettings()` | `tenantApi` | 学员无法进入排期浏览页（约课主入口） |

补充背景：miniapp 构建链路（`uni build`）不做 TypeScript 类型检查，导致此类"引用了未导入符号"的错误无法被构建拦截，直接流入运行时。类型检查门禁属于 Feature 3.2，不在本 Feature 范围。

## 3. User Story

- 作为**教师**，我希望在小程序中打开"我的排期"页面时能正常看到本周课程安排，以便安排教学工作。
- 作为**教师**，我希望打开"学员管理"页面时能看到今日排期及对应预约学员名单，以便进行签到等操作。
- 作为**学员**，我希望打开"排期浏览"页面时能正常加载课程排期与租户配置，以便完成约课。

## 4. Scope

仅以下 3 个文件的 import 补全，不改变任何业务逻辑：

| # | 文件 | 改动 |
|---|------|------|
| 1 | `apps/miniapp/src/pages/teacher/schedule/index.vue` | 补充 `import { extractList } from '@/utils/helpers'` |
| 2 | `apps/miniapp/src/pages/teacher/students/index.vue` | 补充 `import { extractList } from '@/utils/helpers'` |
| 3 | `apps/miniapp/src/pages/student/schedule/index.vue` | 补充 `tenantApi` 的导入（`from '@/api'`，与文件中其他 api 导入风格保持一致） |

前置事实（已在选型阶段只读核查确认）：

- `extractList` 已实现并导出：`apps/miniapp/src/utils/helpers.ts:29`
- `tenantApi` 已实现并导出：`apps/miniapp/src/api/index.ts:538`

## 5. Out of Scope

以下内容**明确不在**本 Feature 内，发现后记录但不顺手修复：

- miniapp 其余 30+ TS 类型错误的清零（属 Feature 3.2 类型检查门禁）
- 任何页面的 loading / empty / error 四态补全（属 Feature 3.4）
- 后端 API、数据库、契约（OpenAPI）的任何变更
- 页面业务逻辑重构、UI 调整、样式优化
- `authApi.sendSms` / `authApi.bindAccount` 死代码清理（P1-20，另行处理）
- `AiAssistant` 组件相关问题（P2-14、P3-7）

## 6. User Roles

| 角色 | 涉及页面 | 进入方式 |
|------|---------|---------|
| 教师（teacher） | `pages/teacher/schedule/index`、`pages/teacher/students/index` | 教师角色登录后进入，页面内 `checkLogin('teacher')` 校验 |
| 学员（student） | `pages/student/schedule/index` | 学员角色登录后进入，页面内 `checkLogin('student')` 校验 |

小程序为学员/教师双角色单端，页面级角色校验由既有 `checkLogin(role)` 完成，本 Feature 不改动鉴权逻辑。

## 7. Business Rules

- 本 Feature 不新增、不修改任何业务规则；页面内既有规则保持不变，包括但不限于：
  - 教师排期页：按周展示，周切换重新拉取 `teacherApi.getSchedules({ start_from, start_to })`。
  - 教师学员页：默认选中今日第一个进行中排期并加载其预约名单（`bookingApi.list({ schedule_id })`）。
  - 学员排期页：`onMounted` 时加载租户配置 `tenantApi.getSettings()`，失败时回退默认取消时限 90 分钟且不阻断页面。
  - 页面卸载后（`isUnmounted`）不再写入响应数据。
- 修复后的数据解析行为以 `extractList` 现有实现为准（兼容 `data` 为数组、`data.items`、`data.list` 三种信封形态），不修改 `extractList` 本身。

## 8. Dependencies

| 依赖 | 状态 |
|------|------|
| 前置 Feature | 无 |
| 后端 / 数据库 / 契约变更 | 无 |
| 外部服务 / 密钥 | 无 |
| 被依赖方 | 无（不阻塞其他 Feature） |
| 目标符号存在性 | ✅ 已验证（helpers.ts:29 / api/index.ts:538） |

## 9. Risks

| 风险 | 等级 | 说明与缓解 |
|------|------|-----------|
| 页面此前从未真正运行过，补 import 后可能暴露下一层运行时错误（如数据结构不匹配、后续逻辑报错） | 中 | 验收标准覆盖"完成主流程操作"而非仅"不报错"；发现的新问题记录为独立缺陷，不在本 Feature 内顺手修复 |
| `extractList` 泛型签名与页面实际返回结构不完全匹配 | 低 | `extractList` 默认为 `any`，风险低；修复时核对 3 处调用实参 |
| 修复范围被扩大（顺手做四态/类型清零） | 低 | 严格按 Scope 执行，验收只针对本 Feature 的 Acceptance Criteria |
| 学员排期页存在其他潜在运行时问题（页面较长，570 行仅为首个崩溃点） | 低 | 验收包含该页面完整主流程冒烟（浏览→打开预约确认页） |

---

## 附：现状证据（审计快照，2026-09-24）

```text
apps/miniapp/src/pages/teacher/schedule/index.vue:190
    schedules.value = extractList(result)        # extractList 未导入

apps/miniapp/src/pages/teacher/students/index.vue:134
    scheduleList.value = extractList(result)     # extractList 未导入
apps/miniapp/src/pages/teacher/students/index.vue:153
    students.value = extractList(result)         # extractList 未导入

apps/miniapp/src/pages/student/schedule/index.vue:570
    const settingsResult = await tenantApi.getSettings()   # tenantApi 未导入
```
