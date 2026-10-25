# F6.11 实施计划：学员端会员卡详情与使用记录

> 日期：2026-10-25。依据 requirement.md（契约冻结）、acceptance.md（A–F 分层）。
> 分工：backend-engineer（T6.11.1）、frontend-engineer（T6.11.2/3/4）、project-architect（复核）。**No DB change（已核对）**。

## 1. 架构决策

### 1.1 先安全前置，再暴露 UI

三类只读端点原本仅租户校验，任一登录用户可读本租户任意卡与全租户流水；先做 UI 会以“合法调用”放大越权面。因此 T6.11.1 独立提交（`e0a10c1`）并通过归属测试后，前端才开工。

### 1.2 契约零变更与混合角色

- 路径、query、响应 DTO 均不变；`card_ids` 仅作 Repository 内部过滤，不对学员暴露。
- 归属判断在 Service 层强制，三端点不挂 `@require_roles`，复用 F6.7 `get_affected_bookings_by_card` 范式。
- admin/super_admin 走原全量分支，学员及其他角色走归属分支。

### 1.3 调用链

```
miniapp 列表/详情/流水 → src/api/index.ts（既有 request）
  → GET /api/v1/membership/cards/{id} | /cards | /transactions
  → membership Service（归属校验）→ Repository（TenantAware）

student-web 列表/详情/流水 → @dance-saas/api-client
  → 同一组 HTTP 端点
```
## 2. 文件白名单

| 组 | 文件 | 改动 |
|----|------|------|
| 后端（T6.11.1） | `membership/service.py`、`repository.py`、`router.py`、`tests/test_membership_requester_scope.py` | 3 个 requester 方法；`card_ids` 过滤；3 端点改调 + `redis_client`；14 例测试 |
| miniapp（T6.11.2） | `pages.json`、`pages/student/membership/{index,detail,transactions}.vue`、`src/api/index.ts` | 2 页注册；详情/流水新建；列表整卡点击；错误 `statusCode` |
| student-web（T6.11.3） | `router/index.ts`、`views/membership/{index,detail,transactions}.vue`、`views/profile/index.vue` | 3 条 `requiresAuth` 路由；三页新建；会员卡菜单跳转 |

**明确禁止**：`packages/api-client`、`packages/api-types`、admin-web、teacher-web、TabBar、DDL/迁移/新端点/新响应字段、购卡/支付/退款/改期 UI。
## 3. 任务拆分

| # | 任务 | Agent | 依赖 | 验收映射 |
|---|------|-------|------|----------|
| T6.11.1 | 后端归属校验 + 14 例测试（已提交 e0a10c1） | backend | — | A-1/A-2、B-1..B-11 |
| T6.11.2 | miniapp 两页 + 列表点击 + 错误状态码 | frontend | T6.11.1 | A-3、C-1.*、D-* |
| T6.11.3 | student-web 三路由/三页 + 个人中心入口 | frontend | T6.11.1 | A-4、C-2.*、D-* |
| T6.11.4 | 四态核对 + 多端构建 + 浏览器实测 + 回归 | frontend | T6.11.2/3 | A-3..A-6、C-3、E-*、F-* |

```
T6.11.1 ──┬─→ T6.11.2（miniapp）──┐
          └─→ T6.11.3（student-web）─┴─→ T6.11.4（验证）
```

T6.11.2 与 T6.11.3 分属不同 app，可并行；T6.11.4 统一收口。
## 4. 关键实现要点

| 任务 | 要点 |
|------|------|
| T6.11.1 | `get_card_for_requester`：先 `get_card`（404/跨租户 404）再 `check_roles`，非 admin 且非本人 → 403；列表非 admin 传他人 `student_id` → 403，否则强制本人；流水非 admin 传 `card_id` 先校验，未传取本人全部卡（无卡空页）；`check_roles` fail-closed |
| T6.11.2 | 详情 `onLoad` 先 `checkLogin('student')`，`card_id` 非法直接 404 文案且不发请求；query 兜底需 `safeDecode`；流水页不用 `page-container`，保证 `onReachBottom`；续页失败回退 `page`；错误对象 `statusCode` 为增量属性 |
| T6.11.3 | 列表不传 `student_id`、`page_size=100` 后前端 Tab 分组；详情 403/404 读 `e.response.status`；流水「加载更多」失败回退页码；`cancelled_*` 用局部交叉类型 |
## 5. 测试与验证

| 层 | 方式 |
|----|------|
| 单测/集成 | 新增 14 例归属矩阵；回归 24 + 9 例 |
| 静态 | `py_compile`、`ruff`、`vue-tsc` |
| 构建 | miniapp `build:mp-weixin`、student-web `build` |
| 运行时 | 真实后端 :8000 接口冒烟 + 浏览器 localhost:5174 点击 |
| 人工 | 微信开发者工具/真机续页（未验证，见 runtime-test-report.md） |
## 6. 风险

| # | 风险 | 等级 | 缓解 |
|---|------|------|------|
| R-1 | `PERMISSION_CHECK_BYPASS=True` 时归属校验失效 | 高（既有债务） | 生产必须 False；本期不依赖该开关 |
| R-2 | 教师是否需查名下学员卡未定 | 中 | 无产品证据，一律 403；登记待决策 |
| R-3 | miniapp `onReachBottom` 与 H5 行为不同 | 中 | 页面可滚动 + `disableScroll:false`；真机未验证 |
| R-4 | api-client 缺 `cancelled_*` | 低 | 局部扩展类型；登记 D-F6.11-1 |
| R-5 | 原型详情与流水同页，本期拆页 | 低 | 按 backlog 拆分；流水课程名/排期字段后端无，已裁剪 |
## 7. UNKNOWN

| # | 问题 | 默认处理 |
|---|------|----------|
| U-1 | 学员端是否需要服务端状态筛选 | 本期前端 Tab 分组，不改 query |
| U-2 | 作废卡的流水是否展示 | 展示（流水为只读历史） |
| U-3 | 教师只读他人卡是否放开 | 不放开，403 |
| U-4 | 流水是否展示操作人 | 不展示（字段最小化） |

## 8. Handoff

- **→ frontend-engineer**：只改白名单 5+5 文件；复用既有请求层；四态齐全；错误文案固定；不渲染内部字段。
- **→ project-architect（复核）**：核对归属矩阵、分层、契约零变更、回滚面。
- **冲突面**：无。两端目录隔离；后端仅 T6.11.1 已合入。
