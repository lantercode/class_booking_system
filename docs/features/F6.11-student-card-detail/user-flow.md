# F6.11 用户流程：学员端会员卡详情与使用记录
> 日期：2026-10-25。契约依据 requirement.md §5（路径/query/DTO 未变）。

## 1. 流程总览

| 流程 | 承载端 | 说明 |
|------|--------|------|
| F-1 | miniapp 列表 → 详情 | 6 组卡卡片整卡可点 |
| F-2 | miniapp 详情 → 使用记录 | 按 `card_id` 分页，触底续页 |
| F-3 | student-web 个人中心 → 列表 → 详情 → 流水 | 三条路由串联 |
| F-4 | 错误分支（两端） | 403 / 404 / 其他文案 |
## 2. F-1：miniapp 列表 → 详情

### 2.1 入口与参数
| 项 | 内容 |
|----|------|
| 列表分组 | 使用中 / 已用尽 / 未激活 / 冻结 / 过期 / 作废 共 6 组 |
| 跳转 | 卡片容器 `@tap="goDetail(card)"` → `navigateTo('/pages/student/membership/detail?...')` |
| query | `card_id` 必传；`card_no`、`product_name` 仅作详情字段缺失兜底（`encodeURIComponent`） |
| 冒泡 | 激活 / 解冻 / 复制卡号保持 `@tap.stop`，不触发跳转 |
### 2.2 加载与错误

- `onLoad` 先 `checkLogin('student')`；`card_id` 缺失/非法 → 「会员卡不存在或已失效」，不发请求。
- 请求 `getCardDetail(card_id)`；loading「加载中...」→ 成功渲染 → 失败错误块 + 「返回列表」。
- 403「无权查看该会员卡」；404「会员卡不存在或已失效」；其他用后端 `msg`。
- `safeDecode` 解析 query，解码异常时回退原文。
### 2.3 详情内容

| 区块 | 展示 | 条件 |
|------|------|------|
| 卡面 | 产品名（兜底「会员卡」）、状态徽标、卡号（兜底 `-`）、卡类型 | 总是 |
| 有效期 | 生效时间、到期时间 | 总是 |
| 课时 | 总次数 / 已使用 / 剩余 | `card_type === 'count'` |
| 冻结信息 | 冻结时间 / 预计解冻 / 冻结原因 | `status === 3` |
| 作废信息 | 作废时间 / 作废原因 | `status === 6` |
### 2.4 操作

| 操作 | 行为 |
|------|------|
| 查看使用记录 | `navigateTo('/pages/student/membership/transactions?card_id={id}')` |
| 去预约 | `redirectTo('/pages/student/schedule/index')` |
| 返回列表 | 有上一页 `navigateBack`，否则 `redirectTo` 列表页 |
## 3. F-2：miniapp 使用记录

### 3.1 加载与续页

- 首屏：`getTransactions({card_id, page:1, page_size:20})` → loading / error / empty / data。
- `onReachBottom` 条件：`!loading && !loadingMore && items.length < total`。
- 续页：`page += 1` → 追加；失败 toast 文案 + `page` 回退。
- 空态「暂无使用记录」；底部「加载中 / 上拉加载更多 / 没有更多了」。
- 页面不套 `page-container`（`overflow:hidden` 阻断滚动），`pages.json` 置 `disableScroll:false`。
### 3.2 列表项字段

| 区域 | 字段 | 格式化 |
|------|------|--------|
| 头部左 | `operation_type` | 中文映射（R-3），未知「其他」 |
| 头部右 | `change_amount` | 正数 `+N` 绿 / 负数红 / 0 灰 |
| 元信息左 | `created_at` | `YYYY-MM-DD HH:mm` |
| 元信息右 | `balance_after` | 「余额 N」 |
| 备注 | `remark` | 空则隐藏 |
| 关联 | `booking_id` | 有值显示「关联预约 #id」 |

> 不渲染 `operator_id` / `idempotency_key` / `public_id`。
## 4. F-3：student-web 会员卡流程

### 4.1 入口与路由

| 步骤 | 行为 |
|------|------|
| 入口 | `/profile` → 「我的会员卡」`@click=goToMembership` → `/membership` |
| 列表 | `/membership`（`requiresAuth`）：`list({page:1,page_size:100})`，不传 `student_id` |
| 详情 | 点击卡 → `/membership/:id`：`membershipCardApi.get(id)` |
| 流水 | 「查看使用记录」→ `/membership/:id/transactions` |
### 4.2 页面行为

| 页面 | 关键行为 |
|------|----------|
| 列表 | Tab：全部/可用/不可用（0/1/3 可用，2/6 不可用）；loading / el-empty / el-result+重试 / 数据 |
| 详情 | 卡面 + 有效期 + 课时（count）+ 冻结/作废；403/404 文案 + 返回列表/重试 |
| 流水 | `getTransactions({card_id,page,page_size:20})`；「加载更多」失败回退页码；字段口径同 miniapp |
## 5. F-4：错误与未登录

| 场景 | miniapp | student-web |
|------|---------|-------------|
| 403 他人卡 | 「无权查看该会员卡」+ 返回列表 | el-result 同文案 + 返回/重试 |
| 404 不存在/跨租户 | 「会员卡不存在或已失效」 | 同文案 |
| 其他错误 | 后端 `msg` 或兜底文案 | 后端 `msg` 或兜底文案 |
| 未登录 | `checkLogin('student')` 拦截 | 路由守卫跳登录并带 `redirect` |

> 跨租户统一 404，不暴露卡是否存在（后端既定行为）。
