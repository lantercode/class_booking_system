# F6.7 发布说明：卡失效替代与受影响预约（D3）

> 状态：**已交付**（2026-10-22 人工验收通过）
> 日期：2026-10-22。效率实验**试点组**样本（M1/M2/M3/M5/M6）。

## Feature

卡被冻结/过期/作废后，系统可查询该卡名下「受影响的有效预约」（BOOKED/CHECKED_IN 且排期未开始）；管理端冻结/作废前展示影响面；学员端预约列表出现警示条，可自助换卡改派，无替代卡时引导联系机构。

## Problem

预约后卡失效，系统零处理，学员到店才发现；管理端作废/冻结前无法评估影响面；学员无自助换卡出口（D3 三层策略的产品诉求）。

## Fix

- 新增 `GET /api/v1/membership/cards/{card_id}/affected-bookings`（K2 单端点 + 角色作用域）：admin/super_admin 查本租户任意卡；其他角色仅本人卡（403）；卡不存在/跨租户 404。
- 查询实现放 `BookingService.get_affected_bookings_by_card`（规避 membership→booking 循环 import）；Repository `list_affected_by_card` JOIN 排期，K1 口径 `status IN (BOOKED, CHECKED_IN) AND start_at > now`，`ORDER BY start_at ASC, id ASC`，分页返回 total+items。
- 链路纯只读；freeze/cancel/reschedule/create_booking 事务路径零改动。
- admin-web：冻结/作废双弹窗内嵌影响面区域（loading/error+重试/empty/success 四态，失败不阻断主操作，≤5 条明细，「以操作时实际为准」；作废 total>0 时按钮 danger「确定作废」）。
- miniapp：预约列表警示条（失效卡 + 未来预约）；BOOKED → 换卡弹层（消费 F6.6 recommend-card，默认选中推荐，提交 F6.5 reschedule + 幂等键）；CHECKED_IN → 仅「请联系机构处理」；空态懒加载机构电话（有号可直拨，无号降级文案）。

## Files Changed

- 后端：`booking/repository.py`、`booking/service.py`、`booking/schemas.py`、`membership/router.py`
- 测试：`apps/api/tests/test_membership_affected_bookings.py`（新增 720 行，24 例）
- 前端：`packages/api-client/src/membership.ts`、`apps/admin-web/src/views/membership/index.vue`、`apps/miniapp/src/api/index.ts`、`apps/miniapp/src/pages/student/bookings/index.vue`
- 生成物：`packages/api-types/openapi.json`、`schema.d.ts`

## Tests

| 集合 | 结果 |
|------|------|
| 新增套件 | **24 passed**（B-1..B-12、C-1..C-10、C-11/C-12 并发专项、E-3），13.08s |
| 并发专项 | 作废/冻结 vs 换卡改派竞态：无 500/死锁；改派成功=一补一扣且 affected=0；失败=零流水不悬空 |
| 定向回归 | F6.6 推荐 9 + F6.5 改期 31 passed |
| 静态 | `py_compile` ×5、`ruff` ×5、gen:types（82 路径）、admin build、miniapp type-check + build 全过 |
| 人工验收 | **通过**（F-1~F-6，2026-10-22） |

## Acceptance

- PASS：A 组（静态 10 项）、B 组（12 例）、C 组（含并发）、D 组（前端 10 项）、E 组（权限矩阵含 teacher）、F 组（人工 6 项）。
- 差异登记：C-9 参数非法实际 422（全局 handler 既有约定），与 acceptance 原文 400 差异 → D-F6.7-2。

## Known Risks

1. 影响面 TOCTOU：admin 看到 N 后学员改派成功，实际作废时数字已变——查询只读 + 文案「以操作时实际为准」，并发专项验证结果可解释。
2. **D-F6.7-3**：miniapp 前端 join 为近似口径（display_status 1/3 + 卡失效 2/3/6），属安全侧超集，权威以后端 K1 为准。
3. **D-F6.7-1**：api-client barrel 未导出 `AffectedBookingsResponse`（白名单限制），admin-web 暂以类型推导替代。
4. U-5：批量作废的聚合影响面本期不做（N 次单卡调用可实现，不进事务）。

## Migration / Rollback

- 无 DB 迁移、无索引/约束变更；事务路径零改动。
- 回滚：端点纯新增可独立回滚后端；但新版 admin/miniapp 依赖该端点，需同批回滚对应前端版本。

## Release Notes

- 兼容变更：仅新增端点与只读能力；F6.5/F6.6 契约不变（换卡复用 reschedule + recommend-card）。
- 发布顺序：后端 → admin-web / miniapp；旧版前端不受影响（无该端点调用）。
- 上线观察：affected-bookings 调用量与分页分布、换卡改派成功率、警示条触发占比、403/404 比例（权限探测监控）。
