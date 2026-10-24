# F3.1 — 静态验证报告

> Feature ID：F3.1
> 验证日期：2026-09-24
> 验证范围：AC-1（静态修复确认）、AC-2（构建与类型）
> 验证性质：只读检查，未修改任何代码

---

## 1. Git 检查执行记录

### 1.1 `git status`

工作区存在大量**历史遗留**的未提交变更（membership/AI/booking 等模块，详见 implementation-report.md），与 F3.1 无关。F3.1 相关的修改文件为：

```
M apps/miniapp/src/pages/teacher/schedule/index.vue
M apps/miniapp/src/pages/teacher/students/index.vue
M apps/miniapp/src/pages/student/schedule/index.vue
```

### 1.2 `git diff --check`（3 个目标文件）

退出码 `0`，无空白符/格式问题。

### 1.3 目标文件 diff 内容

**teacher/schedule/index.vue**（numstat：+1 / -0）：

```diff
+import { extractList } from '@/utils/helpers'
```

**teacher/students/index.vue**（numstat：+1 / -0）：

```diff
+import { extractList } from '@/utils/helpers'
```

**student/schedule/index.vue**（numstat：+36 / -10），diff 包含两部分：

a) 本次 F3.1 修改（import 行）：

```diff
-import { bookingApi, courseTypeApi, membershipApi, scheduleApi } from "@/api";
+import { bookingApi, courseTypeApi, membershipApi, scheduleApi, tenantApi } from "@/api";
```

b) **预存未提交改动**（`validateCardForSchedule` 区域 L369-444，会员卡校验文案/原因细分逻辑）：本次会话未触碰。已通过 `git show HEAD:` 比对确认该部分在 F3.1 实施前即存在于工作区。

### 1.4 范围检查结论

| 检查项 | 结果 |
|--------|------|
| 无关文件修改（本次会话引入） | ✅ 无 |
| 大范围格式化 | ✅ 无（diff --check 通过，import 风格与文件既有引号风格一致） |
| 自动修复产生的额外 diff | ✅ 无 |
| 业务逻辑变更（本次会话引入） | ✅ 无 |
| student 页 git diff 含预存业务改动 | ⚠️ 存在，非本次引入（见 1.3-b） |

---

## 2. 构建 / 类型 / Lint 执行记录

脚本来源：`apps/miniapp/package.json`（实际读取，未假设）。可用脚本：`dev:h5`、`build:h5`、`dev:mp-weixin`、`build:mp-weixin`、`build:mp-weixin:dev`。**无 lint 脚本、无 typecheck 脚本**（vue-tsc 存在于 devDependencies，需 npx 直调）。

| # | 检查 | 命令 | 结果 |
|---|------|------|------|
| 1 | Build | `npm run build:mp-weixin` | ✅ `DONE Build complete.` |
| 2 | 构建产物抽查 | 检查 `dist/build/mp-weixin/pages/teacher/schedule/index.js` | ✅ 编译产物包含 `extractList` 有效引用；3 个页面产物目录均正常生成 |
| 3 | TypeScript | `npx vue-tsc --noEmit` | 27 个错误（修复前 30+），`extractList`/`tenantApi` 相关错误 **0** 个 |
| 4 | Lint | — | ⚪ N/A（package.json 无 lint 脚本，项目未配置） |

剩余 27 个 TS 错误全部为历史遗留（分布：teacher/schedule/form.vue 6、student/bookings 5、student/schedule 4、booking-confirm 3、AiAssistant 3、courses 2、api/index.ts 2、teacher/profile 1、courses/detail 1），清零属 F3.2 Scope。其中 student/schedule 的 4 个错误（L197/L396/L406/L572）均不在本次修改行（L148）。

---

## 3. AC 逐条判定

### AC-1 静态修复确认

| # | 验收项 | 判定 | 依据 |
|---|--------|------|------|
| AC-1.1 | teacher/schedule 已导入 `extractList` | **PASS** | diff 唯一新增行，路径 `@/utils/helpers` 正确 |
| AC-1.2 | teacher/students 已导入 `extractList` | **PASS** | diff 唯一新增行，路径正确 |
| AC-1.3 | student/schedule 已导入 `tenantApi` | **PASS** | L148 import 行追加，来源 `@/api` 正确 |
| AC-1.4 | 除 import 外无业务逻辑改动 | **FAIL（按 git diff 字面判定）** | `student/schedule/index.vue` 的 git diff 含 `validateCardForSchedule` 业务逻辑改动（+36/-10 中的非 import 部分）。**已确认该改动为 F3.1 实施前的预存未提交修改，非本次会话引入**；教师两页 PASS |
| AC-1.5 | 未改动 helpers.ts / api/index.ts / 其他文件 | **PASS** | 本次会话变更文件数 = 3，均为目标页面文件 |

### AC-2 构建与类型

| # | 验收项 | 判定 | 依据 |
|---|--------|------|------|
| AC-2.1 | `uni build -p mp-weixin` 构建成功 | **PASS** | exit 0，`DONE Build complete.` |
| AC-2.2 | 构建产物含符号有效引用 | **PASS** | 产物 js 中检出 `extractList` 引用，3 页面产物齐全 |
| AC-2.3 | TS 错误数不增加 | **PASS** | 30+ → 27，目标符号相关错误清零，无新增 |
| Lint | 项目已有则执行 | **N/A** | miniapp 未配置 lint 脚本 |

---

## 4. 最终判定

| 用例组 | 判定 |
|--------|------|
| **AC-1** | **FAIL**（条件性）— 唯一失败项 AC-1.4，根因是 student 页携带的**预存未提交改动**混入 git diff，并非 F3.1 修复本身越界 |
| **AC-2** | **PASS**（3/3 通过，Lint N/A） |

## 5. 问题报告（不修改代码，仅报告）

**问题**：AC-1.4 无法在当前工作区状态下纯以 `git diff` 判定 PASS。

- **事实**：`apps/miniapp/src/pages/student/schedule/index.vue` 工作区版本相对 HEAD 有 +36/-10 行差异，其中仅 L148 一行为 F3.1 的 import 修复，其余为预存的 `validateCardForSchedule` 改动（会员卡未激活/冻结/过期的细分提示逻辑）。
- **影响**：不影响 F3.1 修复正确性；影响验收口径与提交粒度——若整文件提交，F3.1 的 commit 将混入无关业务改动。
- **处置选项（由用户决定）**：
  1. 接受现状，AC-1.4 按"本次会话改动口径"判 PASS，提交时人工说明；
  2. 用户确认预存改动归属后，拆分提交（`git add -p` 或先提交预存改动）；
  3. 若预存改动为废弃内容，由用户决定还原后重新验证。

**其余事项**：
- Lint 未执行（项目未配置），如需门禁属 F3.2/CI 范畴。
- 运行时验收（AC-3~AC-7）仍需微信开发者工具人工执行。
