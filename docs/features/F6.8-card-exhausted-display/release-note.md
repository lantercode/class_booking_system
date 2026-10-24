# F6.8 发布说明：次卡余额用尽展示（D2）

> 状态：**已交付**（2026-10-24 人工验收通过）
> 日期：2026-10-24。效率实验**试点组**样本 2（L2，启用 M1/M2/M3/M5/M6）。

## Feature

不新增 `EXHAUSTED` 状态，在前端以灰显卡片 + "已用完"徽标 + 提示文案表达次卡余额用尽。

## Problem

次卡用完后 `remaining_credits=0` 仍为 `ACTIVE`，学员/管理员无法直观区分"在用"与"已用完"，且选卡时需明确不可用。

## Fix

- miniapp 会员卡列表：已用卡（`status=1` + `card_type=count` + `remaining_credits=0`）灰显（opacity 降低）+ "已用完"徽标 + 提示文案"次数已用完，请续卡或换卡"。
- admin-web 会员卡列表：ACTIVE 次卡余额 0 时，状态标签后追加灰色"（已用完）"辅助文案，不新增筛选项。
- booking-confirm 不改动：F6.6 后端 `recommend-card` 已排除已用卡。

## Files Changed

- `apps/miniapp/src/pages/student/membership/index.vue`（+50/-1：`card-used-up` 灰显、徽标、提示文案）
- `apps/admin-web/src/views/membership/index.vue`（+14：`isUsedUp` 函数 + 状态列辅助文案）

## Verification

- miniapp：`pnpm type-check` 0 error + `pnpm build:mp-weixin` Build complete。
- admin-web：`pnpm build` ✓ 3.62s。
- L2 自查 diff：口径与 D2 一致；无白名单外改动。
- 人工验收：通过（2026-10-24）。

## Notes

- 不涉及后端/DB/枚举/扣次规则/事务/权限变更。
- K2 因 miniapp 无独立详情页，"已用完"标签与文案内联在已用卡卡片内，效果等价。
- 无技术债。

## Rollback

- 前端回滚仅需 revert 上述 2 文件；无后端/DB 依赖。
