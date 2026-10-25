# F6.11 需求：学员端会员卡详情与使用记录

> 来源：`docs/delivery/feature-backlog.md` §F6.11（L627-643）、任务记录 `docs/engineering/task-records/20261025-F6.11-membership-requester-scope.md`。日期：2026-10-25。
> 风险等级 **L4**（T6.11.1 鉴权/越权）+ **L3**（双端前端）。**No DB change（已核对）**。

## 1. Stage 1 READY 结论

| 项 | 结论 |
|----|------|
| Selected Feature | F6.11 学员端卡详情与流水（miniapp + student-web） |
| Why | miniapp 有 `getCardDetail`/`getTransactions` 但无页面；student-web 无 membership 引用；后端三类只读端点此前仅租户校验，可越权读他人卡与全租户流水 |
| Safety Gate | T6.11.1 归属校验已合入（`e0a10c1`），UI 才允许暴露 |
| Dependencies | F6.3/F6.8 会员卡与流水契约；F6.10 管理端流水口径 |
| Missing | miniapp 两页与列表入口；student-web 三路由/三页与入口；miniapp 错误对象缺 `statusCode` |
| Risks | 见 implementation-plan.md §6 |
| Agents | backend-engineer（T6.11.1）、frontend-engineer（T6.11.2/3）、project-architect（复核） |
| Definition of Ready | **READY**：归属矩阵由 14 例单测 + 真实接口冒烟锁定；路径/query/DTO 不变 |

### 1.1 安全前置（T6.11.1，已提交）

| 端点 | admin / super_admin | 学员及其他角色 |
|------|----------------------|----------------|
| `GET /membership/cards/{id}` | 本租户任意卡 200 | 本人 200 / 他人 403 / 跨租户或不存在 404 |
| `GET /membership/cards` | 全租户，可按 `student_id` 筛选 | 强制本人；显式传他人 `student_id` → 403 |
| `GET /membership/transactions` | `card_id` 可选，全租户 | 传 `card_id` 须为本人卡；不传则聚合本人全部卡 |

实现：Service 新增 3 个 requester 方法；Repository `list_transactions` 增 `card_ids` IN 过滤；Router 三端点注入 `redis_client` 并改调新方法；混合角色端点不挂角色装饰器。
## 2. 现状与缺口

| # | 现状 | 缺口 |
|---|------|------|
| 1 | miniapp `pages.json:140` 仅列表页；6 组卡卡片无点击 | 无详情页/使用记录页，无法进入详情 |
| 3 | miniapp 错误对象只有 `message` | 无法区分 403 / 404 文案 |
| 4 | student-web 无 `/membership` 路由与页面 | Web 端无法查看会员卡 |
| 5 | 个人中心「我的会员卡」菜单无跳转 | 入口点击无响应 |
| 6 | api-client `MembershipCard` 无 `cancelled_*` | 前端局部扩展类型（D-F6.11-1） |

## 3. Scope

| In Scope | Out of Scope |
|----------|--------------|
| miniapp `pages.json` 新增详情/流水页（主包普通页，`disableScroll:false`，TabBar 不动） | 购卡/支付（F6.1）、退款（F6.9）、改期 UI（F6.5） |
| miniapp 详情页只读展示卡号/产品/状态/有效期/次卡课时/冻结/作废 | T6.11.1 之外的任何后端端点/字段/DDL |
| miniapp 流水页按 `card_id` 分页 + `onReachBottom` 续页 | TabBar、admin-web、teacher-web UI 调整 |
| miniapp 6 组卡整卡可点，激活/解冻保持 `@tap.stop` | student-web 服务端状态筛选（本期前端分组） |
| miniapp `api/index.ts` 错误对象增量 `statusCode` | `packages/api-client` / `api-types` 变更 |
| student-web 三路由 `requiresAuth` + 列表/详情/流水三页 | 原型 P-M2 同页方案与流水课程名/排期字段（DTO 无，已裁剪） |
| 个人中心「我的会员卡」绑定 `/membership` | 教师角色只读放开（无产品证据，维持 403） |

## 4. 业务规则

| # | 规则 |
|---|------|
| R-1 | 学员仅能查看本人卡与流水；他人 403，跨租户/不存在 404，前端不得推断归属 |
| R-2 | 状态与分组：0 未激活 / 1 正常 / 2 已过期 / 3 已冻结 / 6 已作废；0、1、3 为「可用」，2、6 为「不可用」（两端一致） |
| R-3 | 流水中文：issue 发放 / consume 扣次 / restore 回补 / recharge 充值 / refund 退款 / adjust 调整 / expire 过期清零；未知「其他」 |
| R-4 | 变动值正数 `+N` 与正向着色，负数负向着色，0 中性色 |
| R-5 | 每页 20 条；miniapp 触底续页，Web「加载更多」；续页失败回退页码 |
| R-6 | 文案：403「无权查看该会员卡」；404「会员卡不存在或已失效」；其余用后端 `msg`，不回显堆栈 |
| R-7 | 详情接口产品名/卡号为空时，miniapp 用列表 query 兜底 |
| R-8 | 本期只读，不新增写操作（激活/解冻仍走列表页）；页面不展示 `operator_id`/`idempotency_key`/`public_id` |
| R-9 | 四态完整：loading / empty / error / data，不空白闪烁 |
| R-10 | 仅经既有请求层（Web `@dance-saas/api-client`，小程序 `src/api/index.ts`），不复制后端校验 |
## 5. 契约（不变）

| 端点 | Query | 响应 |
|------|-------|------|
| `GET /membership/cards/{id}` | Path `card_id` | `MembershipCardResponse` |
| `GET /membership/cards` | `page`/`page_size`/`student_id`/`product_id`/`card_type`/`status`/`keyword` | `{total,page,page_size,items}` |
| `GET /membership/transactions` | `page`/`page_size`/`card_id`/`operation_type` | `{total,page,page_size,items}` |

- 卡消费字段：`id`/`card_no`/`product_name`/`card_type`/`status`/`valid_from`/`expire_at`/`total_credits`/`used_credits`/`remaining_credits`/`frozen_*`/`cancelled_*`。
- 流水消费字段：`id`/`card_id`/`booking_id`/`operation_type`/`change_amount`/`balance_after`/`remark`/`created_at`。
- 不消费：`operator_id`/`idempotency_key`/`public_id`/`student_id`/`student_phone`；OpenAPI 无 diff，`api-types` 未重生成。

## 6. 四端影响面

| 端 | 影响 |
|----|------|
| miniapp | **改**：新增 2 页 + 列表点击 + 错误状态码 |
| student-web | **改**：3 路由/3 页 + 入口跳转 |
| admin-web | 不改；管理端仍走 admin 全量分支，回归覆盖 |
| teacher-web | 不改；教师按非 admin 处理，访问他人卡 403 |
## 7. 用户故事

| # | 角色 | 故事 |
|---|------|------|
| US-1 | 学员（小程序） | 从「我的会员卡」点进任一卡，查看卡号、状态、有效期与剩余课时 |
| US-2 | 学员（小程序） | 查看某张卡的使用记录，理解扣次/回补与变动后余额 |
| US-3 | 学员（Web） | 从个人中心进入列表，按可用/不可用筛选并查看详情与流水 |
