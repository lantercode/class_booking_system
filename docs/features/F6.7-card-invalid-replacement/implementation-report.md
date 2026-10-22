# F6.7 实施报告

> 日期：2026-10-22。执行：backend-engineer（T6.7.1/T6.7.2/T6.7.5 后端）+ frontend-engineer（T6.7.3/T6.7.4），主 Agent 收口。

## 1. Changed Files（白名单内）

| # | 文件 | 类型 |
|---|------|------|
| 1 | `apps/api/src/app/modules/booking/repository.py` | 修改（新增 `list_affected_by_card`，L421-469） |
| 2 | `apps/api/src/app/modules/booking/service.py` | 修改（新增 `get_affected_bookings_by_card`，L1234-1304，只读） |
| 3 | `apps/api/src/app/modules/booking/schemas.py` | 修改（`AffectedBookingItem` / `AffectedBookingsResponse`，L90-111） |
| 4 | `apps/api/src/app/modules/membership/router.py` | 修改（`GET /cards/{card_id}/affected-bookings`，L292-319） |
| 5 | `apps/api/tests/test_membership_affected_bookings.py` | 新增（720 行，24 例） |
| 6 | `packages/api-types/openapi.json` / `schema.d.ts` | 生成（`pnpm gen:types`，82 路径） |
| 7 | `packages/api-client/src/membership.ts` | 修改（类型 + `getAffectedBookings`） |
| 8 | `apps/admin-web/src/views/membership/index.vue` | 修改（冻结/作废双弹窗影响面区域） |
| 9 | `apps/miniapp/src/api/index.ts` | 修改（`bookingApi.reschedule`、`membershipApi.getAffectedBookings`） |
| 10 | `apps/miniapp/src/pages/student/bookings/index.vue` | 修改（警示条、换卡弹层、空态） |

## 2. Exact Changes

### 2.1 后端
- Repository：JOIN CourseSchedule，`status IN (BOOKED, CHECKED_IN)` 且 `start_at > now`（UTC），显式 `tenant_id`，`ORDER BY start_at ASC, id ASC`，返回 `(total, items)`，无 N+1。
- Service（booking 模块，避免循环 import）：`get_card` 复用 404/跨租户屏蔽 → `check_roles` 判 admin → 非 admin 非本人 `PermissionException(403)` → 只读组装。**未触碰** freeze/cancel/reschedule/create_booking 事务路径。
- 端点：无 `@require_roles`（混合角色），`redis_client` DI；路由内零业务判断。
- 无 DB 迁移、无索引改动。

### 2.2 admin-web
- 冻结/作废双弹窗内嵌影响面：loading 骨架 / error+重试（不阻断主操作）/ empty / success（警示条 + ≤5 条明细 +「以操作时实际为准」）；作废弹窗 total>0 时确定按钮 danger 且文案「确定作废」。

### 2.3 miniapp
- 预约列表并行加载 my-cards，join 失效卡（status 2/3/6）+ 有效预约（display_status 1/3）渲染警示条。
- BOOKED →「换卡」弹层（消费 recommend-card、默认选中推荐卡、提交 reschedule + 幂等键随弹层生成、层内重试复用）；CHECKED_IN → 仅「请联系机构处理」。
- 空态懒加载 `tenant/info.contact_phone`：有号渲染「联系机构」（makePhoneCall），无号降级文案「请联系机构前台处理」。

## 3. Tests Run

| 项 | 结果 |
|----|------|
| 新套件 `test_membership_affected_bookings.py` | **24 passed**（B-1..B-12、C-1..C-10、C-11、C-12、E-3），13.08s |
| 并发专项 C-11/C-12 | PASS（冻结/作废 vs 改派竞态：无 500/死锁；改派成功=一补一扣且 affected=0；失败=零流水） |
| 定向回归 | `test_card_recommendation.py` 9 passed；`test_booking_reschedule.py` 31 passed |
| `py_compile` ×5 / `ruff` ×5 | 全过 / 0 error |
| `pnpm gen:types` | PASS（82 路径，无尾斜杠变体） |
| admin-web `pnpm build`（vue-tsc -b + vite） | PASS |
| miniapp `pnpm type-check` + `build:mp-weixin` | 0 error / Build complete |

## 4. Scope Verification

- 实际改动 ⊆ 白名单；生成物仅重新生成未手改；student-web / teacher-web / 迁移文件 / 既有事务路径均未触碰。
- 工作区历史未提交改动未回滚、未覆盖。

## 5. 偏离与决策

| # | 内容 | 处置 |
|---|------|------|
| 1 | C-9 acceptance 写 400，实际 FastAPI 全局 handler 返回 422（既有约定，error_handler.py:82 不覆盖） | 测试按 422 断言并注明；严格 400 需改全局 handler，超白名单，登记差异 |
| 2 | 作废弹窗确定按钮原 primary → total>0 时 danger「确定作废」 | 按 F-2 警示语义调整 |
| 3 | api-client barrel 未导出 `AffectedBookingsResponse`（白名单限制） | admin-web 用 `ReturnType` 推导替代，登记后续补导出 |

## 6. Risks / UNKNOWN

- 影响面 TOCTOU（R-1）：查询只读 + 文案「以操作时实际为准」；并发专项已验证结果可解释。
- R-5 关闭：C-11 顺带验证旧卡作废后 `restore_credit` 回补无双扣。
- U-2：recommend-card `message` 原样展示（F6.6 契约不变）。
- my-cards 加载失败时警示静默降级（符合四态表）。

## 7. Handoff

- Stage 10：project-architect 复核（对照 acceptance A–F 与真实改动）。
- Stage 11：用户人工验收（admin 弹窗影响面、miniapp 警示/换卡/空态、权限拒绝）。
