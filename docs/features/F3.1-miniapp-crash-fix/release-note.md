# F3.1 — Release Note

> Feature ID：F3.1
> 关闭日期：2026-09-26
> 状态：✅ DONE（人工验收通过）
> Review 结论：READY_FOR_ACCEPTANCE

---

## Feature

**miniapp 运行时崩溃修复**（Epic 3 / Phase 1 / P0-8、P0-9、P0-10）

## Problem

小程序 3 个核心页面因缺失 import 在运行时抛出 `ReferenceError`，核心流程不可用：

| 页面 | 崩溃点 | 缺失符号 | 真实症状 |
|------|--------|---------|---------|
| 教师排期 `pages/teacher/schedule/index.vue:190` | `extractList(result)` | `extractList` | 数据加载失败，页面功能失效 |
| 教师学员 `pages/teacher/students/index.vue:134,153` | `extractList(result)` ×2 | `extractList` | 排期选项与学员列表均无法加载 |
| 学员排期 `pages/student/schedule/index.vue:570` | `tenantApi.getSettings()` | `tenantApi` | 租户配置静默降级为默认 90 分钟（异常被既有 try/catch 吞没） |

**根因**：`uni build`（esbuild）构建不做类型检查，未定义标识符不会在构建期暴露，流入运行时才触发 ReferenceError。被引用的 `extractList` / `tenantApi` 实现早已存在，缺的只是 import 语句。

## Fix

每个文件补充 1 行 import，共 3 行改动。零业务逻辑变更。

## Files Changed

| 文件 | 变更 |
|------|------|
| `apps/miniapp/src/pages/teacher/schedule/index.vue` | +1 行：`import { extractList } from '@/utils/helpers'` |
| `apps/miniapp/src/pages/teacher/students/index.vue` | +1 行：`import { extractList } from '@/utils/helpers'` |
| `apps/miniapp/src/pages/student/schedule/index.vue` | L148 既有 `@/api` 导入行追加 `tenantApi` |

未改动 `utils/helpers.ts`、`api/index.ts` 或任何其他文件。

## Tests

| 阶段 | 结果 | 报告 |
|------|------|------|
| 静态验证（git diff 范围 / 构建 / vue-tsc） | ✅ 通过（构建成功；TS 错误 30+ → 27，无新增） | static-verification.md |
| Runtime 回归（H5 浏览器自动化 + API 直测） | ✅ 17 PASS / 0 FAIL / 6 UNKNOWN | runtime-test-report.md |
| 微信开发者工具人工验收 | ✅ 通过（2026-09-26） | 人工执行 |

关键验证点：
- 3 页面加载无 `extractList is not defined` / `tenantApi is not defined`
- API 认证链路：无 token 401 / 无效 token 401 / 有效 token 200
- 页面级 checkLogin 拦截正常
- 控制台无未捕获异常

## Acceptance

- AC-1（静态修复确认）：✅（AC-1.4 按"本次会话改动口径"判定，学员页预存改动确认为非本次引入）
- AC-2（构建与类型）：✅ 3/3 通过（Lint N/A——miniapp 未配置）
- AC-3 ~ AC-7（运行时）：✅ 17 PASS / 0 FAIL；6 项 H5 环境保真度限制的 UNKNOWN 已由微信开发者工具人工验收覆盖

## Known Risks

| 风险 | 状态 |
|------|------|
| 学员页预存未提交改动（`validateCardForSchedule`）归属待定 | 已登记为技术债 D-F3.1-3，待用户决策 |
| 剩余 27 个存量 TS 错误（含 tenantApi 返回类型 `{}`） | 已纳入 F3.2 Scope，并登记 D-F3.1-2 |
| miniapp 无 lint 门禁 | 已登记为技术债 D-F3.1-1 |

## Release Notes

**修复**
- 修复教师端"排期"页加载失败的问题
- 修复教师端"学员"页排期选项与学员列表无法加载的问题
- 修复学员端"排期"页租户取消时限配置读取失败、静默使用默认值的问题

**影响面**：仅小程序端 3 个页面；不涉及后端 API、数据库、管理端/学员端/教师端 Web。

**升级须知**：无 schema / API / 配置变更，直接部署即可。
