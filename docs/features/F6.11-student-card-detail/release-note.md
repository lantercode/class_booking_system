# F6.11 发布说明

- Feature：学员端会员卡详情与使用记录
- 日期：2026-10-25
- 风险等级：L4（T6.11.1 鉴权）+ L3（前端）
- 前置：T6.11.1 归属校验已合入（`e0a10c1`）

## 1. 变更内容

| # | 端 | 变更 |
|---|----|------|
| 1 | API | 三类只读端点补齐学员归属校验：`GET /membership/cards/{id}`、`GET /membership/cards`、`GET /membership/transactions` |
| 2 | API | 新增 Service `get_card_for_requester` / `list_cards_for_requester` / `list_transactions_for_requester`；Repository `card_ids` 过滤 |
| 3 | miniapp | 新增「会员卡详情」「使用记录」两页；列表 6 组卡整卡可点；错误对象带 `statusCode` |
| 4 | student-web | 新增 `/membership`、`/membership/:id`、`/membership/:id/transactions` 与三页；个人中心入口打通 |

无 DB 迁移；无新端点；无响应字段变更；OpenAPI 无 diff。

## 2. 版本影响（4 端）

| 端 | 影响 | 说明 |
|----|------|------|
| miniapp | **需重新发版** | 新增页面需随包发布；旧版本用户无入口，不影响既有功能 |
| student-web | **需重新部署** | 新增路由与页面，静态资源需更新 |
| admin-web | 无影响 | 走 admin 分支，行为不变；回归 24 + 9 例通过 |
| teacher-web | 无影响 | 教师访问他人卡按非 admin 处理 403 |

后端可独立先行发布：旧前端不调用新逻辑，行为等价于现状；归属校验会收紧越权读取，属安全修复。

## 3. 部署与配置

| # | 项 | 要求 |
|---|----|------|
| 1 | `PERMISSION_CHECK_BYPASS` | 生产必须 `False`，否则归属校验失效 |
| 2 | Redis | 归属校验依赖 `check_roles` 权限缓存，Redis 必须可达 |
| 3 | 类型产物 | 无需运行 `gen:types`（无 OpenAPI diff） |

## 4. 回滚方式

| 层 | 操作 |
|----|------|
| API | 还原 3 个 router 调用点：`get_card` / `list_cards` / `list_transactions`（新 Service 方法可保留，不被调用即无影响）；如需彻底回退可一并移除 3 方法与 `card_ids` 过滤 |
| miniapp | 回退 `pages.json` 两页注册；删除 `pages/student/membership/detail.vue`、`transactions.vue`；还原 `membership/index.vue` 的 `goDetail` 与 `api/index.ts` 的 `statusCode` |
| student-web | 还原 `router/index.ts` 三条路由；删除 `views/membership/{index,detail,transactions}.vue`；还原 `profile/index.vue` 菜单绑定 |

无数据副作用，无需数据回滚。

## 5. 技术债登记

| # | 编号 | 内容 | 建议 |
|---|------|------|------|
| 1 | **D-F6.11-1** | `packages/api-client` 的 `MembershipCard` 未声明 `cancelled_at` / `cancelled_reason`，student-web 详情页用局部交叉类型读取 | 后端已有字段，后续在 api-client 补声明并移除局部类型 |
| 2 | （遗留） | 个人中心「我的会员卡」右侧计数仍为 `--` | 需求未要求，另行评估 |
| 3 | （观察） | 流水响应仍下发 `operator_id` / `idempotency_key`，UI 不展示 | 评估按角色裁剪 DTO，需契约评审 |

## 6. 验收与未验证

| # | 项 | 状态 |
|---|----|------|
| 1 | 双端构建 | ✅ 通过 |
| 2 | 后端归属矩阵 | ✅ 14 passed + 真实接口冒烟 |
| 3 | 浏览器列表/详情/403/404 | ✅ 通过 |
| 4 | 小程序真机续页 | **NOT VERIFIED** |
| 5 | 流水页浏览器 UI 实测 | **NOT VERIFIED** |
| 6 | student-web 服务端状态筛选 | **NOT VERIFIED** |
