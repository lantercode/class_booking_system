# F6.6 静态验证

> 日期：2026-10-22。判定词：PASS / FAIL / BLOCKED。

| # | 验收项 | 证据 | 结果 |
|---|--------|------|------|
| A-1 | Router 薄层 | `router.py` 新增端点仅参数/依赖/Service 调用/`success()`，无业务判断与查询 | PASS |
| A-2 | 跨模块只调 Service | `recommend_card_for_schedule` 调用 `ScheduleService().get_schedule_by_id`，未查 schedule 表 | PASS |
| A-3 | 租户隔离 | 卡数据走 `get_all_cards_by_student(student_id, tenant_id)`；排期经租户感知 Service | PASS |
| A-4 | 只读、无锁 | 方法内无 `commit/flush`、无 `FOR UPDATE`、无流水写入 | PASS |
| A-5 | 判定单一来源 | `is_bookable_card` 委托 `card_unavailable_reason`；推荐链路复用并仅追加余额规则 | PASS |
| A-6 | 契约 | `openapi.json` diff 仅新增 `/api/v1/membership/recommend-card`；`my-cards` 无变化 | PASS |
| A-7 | 生成类型 | `pnpm gen:types` 生成 `openapi.json` + `schema.d.ts`，无手改 | PASS |
| A-8 | Python 语法 | `py_compile service.py router.py` 通过 | PASS |
| A-9 | Lint | 改动文件 `ruff check` → All checks passed；全目录仅存量 `schemas.py:330 W292` | PASS（存量不计） |
| A-10 | 小程序构建 | `pnpm type-check` PASS；`pnpm build:mp-weixin` PASS | PASS |

## 范围核对

| 项 | 结果 |
|----|------|
| 后端实际改动 | `membership/service.py`、`membership/router.py` |
| 测试新增 | 2 个文件（27 用例） |
| 小程序实际改动 | `api/index.ts`、`booking-confirm/index.vue` |
| 生成物 | `packages/api-types/openapi.json`、`schema.d.ts` |
| 白名单外改动 | 无（`schemas.py` 未修改，仅存量 lint 提示） |
| 未覆盖用户改动 | 历史未提交改动保持原样 |

## 结论

**STATIC PASS**，可进入运行时验证与 Review。
