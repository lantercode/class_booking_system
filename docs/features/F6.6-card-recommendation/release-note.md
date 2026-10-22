# F6.6 发布说明：多卡默认推荐策略（D6）

> 状态：**已交付**（2026-10-22 人工验收通过）
> 日期：2026-10-22

## Feature

学员预约时，由后端按统一策略给出默认推荐会员卡，并返回严格排序的可用卡列表与不可用原因；小程序不再维护本地推荐规则。

## Problem

小程序 `booking-confirm` 在本地按 `unlimited → period → count` 且次卡剩余次数**降序**选卡，与 D6「先过期优先 → 剩余次数少优先 → 同分先发放」相反且缺失过期维度；同时本地自行过滤过期/作废卡，与后端 `is_bookable_card` 存在规则漂移。

## Fix

- 新增 `GET /api/v1/membership/recommend-card?schedule_id=`（学员读本人数据，无新增权限点）。
- `MembershipCardService.recommend_card_for_schedule` 只读链路：跨模块调用 `ScheduleService.get_schedule_by_id`，排期租户不匹配返回 404；卡集合复用 `get_all_cards_by_student`。
- 抽出共享判定 `card_unavailable_reason`（状态 / 排期日有效期 / 课程适用性 / 未知卡类型），`is_bookable_card` 改为委托，行为保持不变；推荐链路再追加「次卡已用完」。
- D6 排序键：`expire_at ASC（NULL 最后）→ remaining_credits ASC（None 最后）→ created_at ASC → id ASC`。
- 响应：`schedule_id`、`recommended_card_id`、`available_cards`（`MembershipCardResponse[]`，按排序输出）、`message`；无可用卡返回 HTTP 200 + `recommended_card_id=null` + `available_cards=[]` + 聚合原因。
- 小程序：`membershipApi.getRecommendCard`；删除 `allCardsWithStatus` / `getDefaultSelectedCard` 本地规则，默认选中后端推荐，选择器严格按后端顺序；空态在卡片区直接展示 `message`。

## Files Changed

- `apps/api/src/app/modules/membership/service.py`
- `apps/api/src/app/modules/membership/router.py`
- `apps/api/tests/unit/test_card_recommendation.py`（新增，18 用例）
- `apps/api/tests/integration/test_card_recommendation.py`（新增，9 用例）
- `apps/miniapp/src/api/index.ts`
- `apps/miniapp/src/pages/student/booking-confirm/index.vue`
- `packages/api-types/openapi.json`、`packages/api-types/schema.d.ts`（生成物）

## Tests

| 集合 | 结果 |
|------|------|
| 新增单测 | 18 passed |
| 新增集成 | 9 passed（含排序稳定、八类排除、空态、401/404、跨租户、只读性、本人卡隔离） |
| 合并运行 | 27 passed |
| 会员卡回归（状态机 / 期卡生命周期 / 期卡下单校验 / 卡授权） | 29 passed |
| 静态 | `py_compile`、`ruff`（改动文件）通过 |
| 契约 | `pnpm gen:types` 通过（81 路径），OpenAPI 与实现逐对象一致 |
| 小程序 | `pnpm type-check`、`pnpm build:mp-weixin` 通过 |
| 人工验收 | **通过**（2026-10-22，默认推荐 / 空态文案 / 推荐卡下单） |

## Acceptance

- PASS：A-1~A-10、B-1~B-10、C-1~C-10、D-1~D-7、E-1~E-4、F-1~F-3。
- NOT VERIFIED：E-4 的 500 分支未构造确定性触发点；已验证 401/404 响应不含 traceback / SQL / 内部地址，沿用全局异常处理。

## Known Risks

1. **D-F6.6-1**（低）：`recommend-card` 使用 `response_model=dict`，OpenAPI 200 为泛型对象，生成类型无法静态校验响应字段；与 `my-cards` 同口径，后续统一建模。
2. **D-F6.6-3**（低）：D6 排序以 `remaining_credits is None` 识别期卡/无限卡，依赖发放时 `total_credits=NULL`；异常数据可能偏离排序口径。
3. **D-F6.6-4**（低）：推荐请求失败与「无可用卡」共用空态渲染，失败时可能被误读为无卡。
4. 期卡区间冲突不在推荐阶段预校验（冻结决策 K4），仍由下单 `validate_period_card_booking` 兜底；推荐卡可能在下单时因冲突被拒。
5. 推荐为只读快照，卡状态/排期容量并发变化以 `create_booking` 行锁与状态重检为最终权威。
6. 已关闭：`D-F6.6-2`（死代码已删除）、`D-F6.6-5`（文档信封已对齐）。

## Migration / Rollback

- 无数据库迁移、无索引与约束变更。
- 代码回滚：端点纯新增，回滚后端不影响 `my-cards` 等其他接口；但新版小程序依赖该端点，**需与小程序版本同批回滚**或临时恢复本地推荐逻辑。
- 数据回滚：不涉及。

## Release Notes

- 兼容变更：仅新增端点与只读能力，`my-cards` 契约与既有字段不变；管理端、student-web 不受影响。
- 发布顺序：先后端、后小程序；旧版小程序继续调用 `my-cards` + 本地规则，可正常预约但推荐口径仍为旧逻辑。
- 上线观察：`recommend-card` 调用量、空态占比、推荐卡与最终下单卡不一致率、下单期卡冲突拒绝率。
