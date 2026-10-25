# F6.11 验收标准：学员端会员卡详情与使用记录
> 日期：2026-10-25。分层：A 静态/构建、B 归属与接口、C 前端功能与四态、D 契约、E 回归、F 人工与未验证。
> 风险等级 L4（T6.11.1 鉴权）+ L3（双端前端）。No DB change（已核对）。

## A. 静态与构建

| # | 项 | 标准 |
|---|----|------|
| A-1 | 后端静态 | `py_compile`（3 业务文件 + 测试）无错误；`ruff check` 通过 |
| A-2 | 归属单测 | `pytest tests/test_membership_requester_scope.py` → 14 passed |
| A-3 | miniapp 构建 | `pnpm --filter dance-miniapp build:mp-weixin` → `vue-tsc --noEmit` 通过 + `DONE Build complete.` |
| A-4 | student-web 构建 | `pnpm --filter student-web build` → `vue-tsc -b && vite build` → `✓ built` |
| A-5 | 契约冻结 | OpenAPI 无 diff；`packages/api-types` 未重生成；`packages/api-client` 未改 |
| A-6 | 分层审查 | Router 只做参数/依赖注入并调 Service；归属判断在 Service；Repository 继承租户仓储 |
## B. 归属矩阵（后端，真实接口冒烟）

| # | 场景 | 账号/角色 | 预期 |
|---|------|-----------|------|
| B-1 | 本人卡详情 | 学员 | 200，返回本人卡 |
| B-2 | 他人卡详情 | 学员 | 403「无权查看该会员卡」 |
| B-3 | 跨租户 / 不存在卡详情 | 学员 | 404（不暴露存在性） |
| B-4 | 任意卡详情 | admin / super_admin | 200，本租户任意卡 |
| B-5 | 卡列表不传 student_id | 学员 | 仅返回本人卡 |
| B-6 | 卡列表传他人 student_id | 学员 | 403「无权查看其他学员的会员卡」 |
| B-7 | 卡列表按 student_id 筛选 | admin | 200，可查本租户任意学员 |
| B-8 | 流水传本人 card_id | 学员 | 200，仅该卡流水 |
| B-9 | 流水传他人 card_id | 学员 | 403 |
| B-10 | 流水不传 card_id | 学员 | 200，聚合本人全部卡；无卡时空页 |
| B-11 | 流水不传 card_id | admin | 200，全租户流水 |
## C. 前端功能与四态

### C-1：miniapp

| # | 用例 | 预期 |
|---|------|------|
| C-1.1 | 列表与闸门 | 6 组卡卡片点击均进详情；激活/解冻不跳转；`card_id` 缺失/非法不发请求 |
| C-1.2 | 详情字段 | 卡号、产品名、状态、有效期、次卡课时、冻结/作废信息按条件展示 |
| C-1.3 | 兜底 | 详情接口 `card_no`/`product_name` 为空时使用列表 query 值 |
| C-1.4 | 详情错误 | 403 / 404 / 其他分别按 R-6 文案；提供返回列表 |
| C-1.5 | 流水加载/续页 | 首屏 `card_id`+`page=1`+`page_size=20`；`onReachBottom` 追加；无更多显示「没有更多了」 |
| C-1.6 | 续页失败 | toast 文案 + 页码回退，可再次触发 |
| C-1.7 | 流水字段 | 类型中文、正负着色、变动后余额、备注、关联预约 |
| C-1.8 | 字段最小化 | 页面无 `operator_id`、`idempotency_key`、`public_id` |
| C-1.9 | 页面注册 | 两页为主包普通页，`disableScroll:false`，TabBar 未改 |

### C-2：student-web

| # | 用例 | 预期 |
|---|------|------|
| C-2.1 | 入口 | 个人中心「我的会员卡」点击进入 `/membership` |
| C-2.2 | 路由守卫 | 三条路由均 `requiresAuth`，未登录跳登录 |
| C-2.3 | 列表请求 | `list({page:1,page_size:100})`，不传 `student_id` |
| C-2.4 | Tab 分组 | 全部/可用/不可用；0/1/3 可用，2/6 不可用，计数正确 |
| C-2.5 | 详情 | 点击卡进入 `/membership/:id`，接口 200 时渲染卡信息 |
| C-2.6 | 错误文案 | `/membership/1932` → 「无权查看该会员卡」+ 返回/重试；`/membership/999999` → 「会员卡不存在或已失效」 |
| C-2.7 | 流水/加载更多 | 进入流水页参数正确；有更多时按钮加载下一页，失败回退页码 |
| C-2.8 | 字段最小化 | 页面无 `operator_id`、`idempotency_key`、`public_id` |

### C-3：四态

| # | 页面 | loading | empty | error | data |
|---|------|---------|-------|-------|------|
| C-3.1 | miniapp 详情 | 加载中块 | 以 404 文案承担（单对象无独立空态） | 错误块 + 返回列表 | 卡信息 |
| C-3.2 | miniapp 流水 | 首屏加载中 | 「暂无使用记录」 | 错误块 + 返回列表 | 列表 + 续页状态 |
| C-3.3 | student-web 列表 | v-loading | el-empty | el-result + 重试 | 卡列表 |
| C-3.4 | student-web 详情 | v-loading | 404 文案 | el-result + 返回/重试 | 卡信息 |
| C-3.5 | student-web 流水 | v-loading | el-empty | el-result + 重试 | 列表 + 加载更多 |
## D. 契约与类型

| # | 项 | 标准 |
|---|----|------|
| D-1 | 路径/参数/字段 | 仅用 req §5 端点与 query；字段名与后端 DTO 一致；无虚构端点 |
| D-2 | 状态枚举 | 0/1/2/3/6 与 `CardStatus` 一致；流水 7 类型与 `TransactionType` 一致 |
| D-3 | 类型缺口 | `cancelled_*` 由前端局部扩展类型读取，未改 api-client（登记 D-F6.11-1） |
## E. 回归

| # | 项 | 标准 |
|---|----|------|
| E-1 | 影响面预约 | `test_membership_affected_bookings.py` 24 passed |
| E-2 | 推荐卡 | `test_card_recommendation.py` 9 passed |
| E-3 | admin / miniapp 既有流程 | admin 会员卡/流水行为不变；激活/解冻/复制卡号不受整卡点击影响 |
## F. 人工验收与未验证

| # | 项 | 状态 |
|---|----|------|
| F-1 | 浏览器实测列表/Tab/详情/403/404 | 已验证（见 runtime-test-report.md） |
| F-2 | 微信开发者工具/真机滚动续页 | **NOT VERIFIED** |
| F-3 | 流水页浏览器 UI 点击实测 | **NOT VERIFIED**（仅构建与代码审查） |
| F-4 | student-web 服务端状态筛选 | **NOT VERIFIED**（当前为前端 Tab 分组） |
| F-5 | 人工验收签字 | 待人工 |
