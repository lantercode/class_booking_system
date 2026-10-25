# F6.11 实施报告

- Feature：F6.11 学员端会员卡详情与使用记录（miniapp + student-web）
- 日期：2026-10-25
- 状态：开发完成待人工验收；T6.11.1 已提交 `e0a10c1`，T6.11.2/3/4 未提交
- 风险等级：L4（安全前置）+ L3（前端）

## 1. 实施范围

| 子任务 | 内容 | 状态 |
|--------|------|------|
| T6.11.1 | 后端三类只读端点学员归属校验 + 14 例测试 | ✅ 已提交 |
| T6.11.2 | miniapp 详情页、使用记录页、列表点击、错误状态码 | ✅ 完成 |
| T6.11.3 | student-web 三路由/三页 + 个人中心入口 | ✅ 完成 |
| T6.11.4 | 四态、双端构建、浏览器实测、回归 | ✅ 完成（含 NOT VERIFIED 项） |

无 DB 迁移；未重新生成 `packages/api-types`；未改 `packages/api-client`。

## 2. 改动清单（14 文件）

| # | 文件 | 任务 | 概要 |
|---|------|------|------|
| 1 | `apps/api/src/app/modules/membership/service.py` | T6.11.1 | 新增 `get_card_for_requester` / `list_cards_for_requester` / `list_transactions_for_requester` |
| 2 | `apps/api/src/app/modules/membership/repository.py` | T6.11.1 | `list_transactions` 增可选 `card_ids` IN 过滤（纯增量） |
| 3 | `apps/api/src/app/modules/membership/router.py` | T6.11.1 | 三只读端点改调 requester 方法并注入 `redis_client` |
| 4 | `apps/api/tests/test_membership_requester_scope.py` | T6.11.1 | 新增 14 例（R-1~R-5 归属矩阵） |
| 5 | `apps/miniapp/src/pages.json` | T6.11.2 | 注册 `pages/student/membership/detail`、`transactions`，`disableScroll:false` |
| 6 | `apps/miniapp/src/pages/student/membership/detail.vue` | T6.11.2 | 新建只读详情页（卡号/产品/状态/有效期/课时/冻结/作废） |
| 7 | `apps/miniapp/src/pages/student/membership/transactions.vue` | T6.11.2 | 新建流水页（`onReachBottom` 续页，page_size=20） |
| 8 | `apps/miniapp/src/pages/student/membership/index.vue` | T6.11.2 | 6 组卡卡片整卡点击进详情；激活/解冻保持 `@tap.stop` |
| 9 | `apps/miniapp/src/api/index.ts` | T6.11.2 | 业务错误对象增量附带 `statusCode` |
| 10 | `apps/student-web/src/router/index.ts` | T6.11.3 | 新增 `/membership`、`/membership/:id`、`/membership/:id/transactions` |
| 11 | `apps/student-web/src/views/membership/index.vue` | T6.11.3 | 列表 + 全部/可用/不可用 Tab（0/1/3 可用，2/6 不可用） |
| 12 | `apps/student-web/src/views/membership/detail.vue` | T6.11.3 | 详情页（403/404 分支） |
| 13 | `apps/student-web/src/views/membership/transactions.vue` | T6.11.3 | 流水页（加载更多） |
| 14 | `apps/student-web/src/views/profile/index.vue` | T6.11.3 | 「我的会员卡」菜单绑定 `router.push('/membership')` |

## 3. 关键实现决策

| # | 决策 | 依据 |
|---|------|------|
| 1 | 归属校验放 Service，Router 不写业务判断 | 分层规则 + F6.7 混合角色范式 |
| 2 | admin/super_admin 走原全量分支 | 管理端现有行为不变，回归测试覆盖 |
| 3 | 学员不传 `card_id` 聚合本人全部卡 | 避免暴露 `card_ids` query，同时支持跨卡流水 |
| 4 | 跨租户统一 404 | 不泄露卡存在性 |
| 5 | miniapp 拆详情页 + 独立流水页 | 按 backlog 拆分；后端 DTO 无课程名/排期字段 |
| 6 | student-web 前端 Tab 分组 | 不改契约；后续可升级为服务端筛选 |
| 7 | 流水不渲染 `operator_id`/`idempotency_key`/`public_id` | 字段最小化 |
| 8 | miniapp 错误对象增量 `statusCode` | 最小改动，不破坏既有调用方 |
| 9 | 详情页 query 兜底卡号/产品名 | 详情接口字段可能为空，避免展示「-」 |

## 4. 依赖

| 依赖 | 说明 |
|------|------|
| T6.11.1 | UI 的阻塞前置，已合入 |
| 既有请求层 | Web 用 `@dance-saas/api-client`；小程序用 `src/api/index.ts`，未新增第三套 |
| 既有枚举 | `CardStatus`（0/1/2/3/6）、`TransactionType`（7 值） |
| 后端端点 | 三只读端点路径/query/DTO 未变 |

## 5. 偏差与遗留

| # | 项 | 说明 |
|---|----|------|
| 1 | 原型 P-M2 同页 | 拆为详情 + 流水两页；流水裁剪课程名/排期 |
| 2 | student-web 主题 | 未套香槟金，沿用自身 Element Plus 页面范式 |
| 3 | 教师角色 | 访问他人卡一律 403，无只读放开 |
| 4 | D-F6.11-1 | api-client `MembershipCard` 缺 `cancelled_at/cancelled_reason`，前端局部扩展 |
| 5 | 菜单计数 | 个人中心「我的会员卡」右侧仍为 `--`，未做数量 |
| 6 | 未验证 | 小程序真机续页、浏览器流水点击实测、服务端筛选（见 runtime-test-report.md） |
