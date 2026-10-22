# F6.7 用户流程：卡失效替代与受影响预约（D3）

> 日期：2026-10-22。契约依据 requirement.md §4（K1–K3 已冻结）。

## 1. 流程总览（D3 三层策略）

| 层 | 策略 | 承载端 | 本 Feature 流程 |
|----|------|--------|----------------|
| a | 卡状态变更时预约列表警示 | admin-web + miniapp | F-1、F-2 |
| b | 学员自助换卡改派 | miniapp | F-3 |
| c | 无替代卡时引导联系机构 | miniapp | F-4 |

---

## 2. F-1：admin 冻结前影响面流程

```
会员卡列表页
  → 点击「冻结」（index.vue:170 openFreezeDialog）
  → 打开冻结弹窗，同时发起 GET /membership/cards/{id}/affected-bookings?page=1&page_size=5
  → 弹窗内影响面区域：
      loading  → 骨架/加载中
      成功     → total > 0：警示条「该卡有 N 个有效预约，冻结后学员可自助换卡或联系机构处理」
                        + 明细预览（前 ≤5 条：课程名 / 开始时间 / 状态）
                 total = 0：中性提示「该卡无受影响预约」
      失败     → 错误条「影响面查询失败，可重试或继续操作」+ 重试按钮（不阻断冻结）
  → 管理员填写冻结天数/原因 → 确定 → POST /cards/{id}/freeze（既有，不变）
  → 成功 toast + 刷新列表
```

交互先例：`handleAdminUnfreeze`（`index.vue:930-963`）先调 `checkConflict` 再分支渲染——本流程同构，差异仅在于影响面查询失败**不阻断**主操作（R-7 警示非阻断）。

## 3. F-2：admin 作废前影响面流程

与 F-1 同构，入口为「作废」（`index.vue:188 openCancelDialog`，弹窗 `:394-414`），警示文案更强：

- total > 0：「该卡有 N 个有效预约。作废后卡不可恢复，这些预约需学员换卡或机构人工处理。」
- 确定按钮在 total > 0 时文案保持「确定作废」（不阻断），样式为 danger（既有）。

## 4. F-3：miniapp 警示 → 自助换卡改派流程

```
预约记录页（pages/student/bookings/index.vue）onMounted
  → 并行加载：bookingApi.list（既有）+ membershipApi.getMyCards（既有 /membership/my-cards）
  → 前端 join：失效卡集合 = my-cards 中 status ∈ {2 EXPIRED, 3 FROZEN, 6 CANCELLED} 的 id 集
  → 对 bookings 中 display_status == 1（BOOKED）且 membership_card_id ∈ 失效卡集合 的卡片：
      渲染警示条「会员卡已冻结/已过期/已作废」+ 「换卡」按钮
  → 点击「换卡」
      → 调 GET /membership/recommend-card?schedule_id={booking.schedule_id}（F6.6 已交付）
      → 有可用卡：弹出选卡弹层（按后端返回顺序，默认选中 recommended_card_id）
      → 确认 → POST /bookings/{booking_id}/reschedule
              body: { new_schedule_id: booking.schedule_id, new_membership_card_id: 选中卡 }
              （K3：同排期纯改派；携带幂等键，小程序网络重试安全）
      → 成功：toast「换卡成功」→ 刷新预约列表与 my-cards
      → 409/400：展示后端 msg（如「目标卡不可用」），停留弹层允许重选
```

注意：

- CHECKED_IN（display_status == 3）且卡失效的预约：仅渲染警示条「会员卡已失效，请联系机构处理」，**不渲染换卡按钮**（R-6，`reschedule_booking` 仅接受 BOOKED）。
- 卡状态文案映射：2→已过期 / 3→已冻结 / 6→已作废（`membership/models.py:49-56`）。
- 本流程**不依赖**新端点（my-cards + 预约列表 join 即可判定）；新端点 student 访问权（K2）用于后续核对与人工客服场景，本期小程序不强制调用。

## 5. F-4：miniapp 无替代卡空态流程

```
F-3 选卡环节 → recommend-card 返回 recommended_card_id == null 且 available_cards == []
  → 弹层渲染空态：「暂无可用替代卡」+ 后端聚合 message（F6.6 契约）
  → 引导区：「请联系机构处理」+ 「联系机构」按钮
      → 复用既有联系方式入口（机构电话/客服，复用 profile/门店信息既有能力，不新增后端）
  → 不提供重试外的其他操作；预约保持原状（不自动取消，Out of Scope）
```

## 6. F-5：权限拒绝流程

| # | 场景 | 请求 | 结果 | 前端表现 |
|---|------|------|------|----------|
| P-1 | 未登录 | 无/失效 token | 401 | api 层自动 refresh→重放；失败清登录态跳登录（既有拦截器，不新增逻辑） |
| P-2 | student 查他人卡 | `GET /cards/{他人卡}/affected-bookings` | 403「无权查看该卡的受影响预约」 | toast 后端 msg |
| P-3 | 跨租户卡 | 卡属于其他租户 | 404「会员卡不存在」（租户自动注入屏蔽） | toast 后端 msg |
| P-4 | admin 查本租户任意卡 | — | 200 | 正常渲染 |
| P-5 | student 查本人卡 | — | 200 | 正常渲染 |
| P-6 | student 改派他人预约 | `POST /bookings/{他人预约}/reschedule` | 403（F6.5 既有，不改动） | toast 后端 msg |

## 7. 状态与异常四态覆盖

| 视图 | loading | empty | error | success |
|------|---------|-------|-------|---------|
| admin 影响面区域 | 查询中骨架 | total=0 中性提示 | 错误条 + 重试（不阻断） | 警示条 + 明细 |
| miniapp 警示条 | 不阻塞列表渲染（join 失败静默降级为无警示） | 无失效卡 → 不渲染 | my-cards 失败 → 不渲染警示（列表主功能优先） | 警示条 + 换卡/联系机构 |
| miniapp 选卡弹层 | 拉取中 | 无替代卡空态（F-4） | 错误 toast + 可重试 | 卡列表 + 默认推荐 |
