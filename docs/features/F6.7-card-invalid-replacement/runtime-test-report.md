# F6.7 运行时测试报告

> 日期：2026-10-22。环境：真实 HTTP + 真实 PostgreSQL/Redis（apps/api `.venv`）。

## 1. 新增套件 `tests/test_membership_affected_bookings.py`（24 例，13.08s，全部 passed）

| 组 | 覆盖 | 结果 |
|----|------|------|
| B-1..B-12 | Service 层：口径（BOOKED/CHECKED_IN/未来 start_at）、排除（已完成/已取消/已开始）、404/403、排序、分页、排期组装 | 11 例 PASS |
| C-1..C-10 | HTTP：admin 任意卡、student 本人卡、非本人 403、跨租户 404、卡不存在 404、未认证 401、空集合、分页边界、参数非法 422、响应字段 | PASS |
| C-11 | 并发专项：作废/冻结 vs 换卡改派竞态（`asyncio.gather`）——无 500/死锁；改派成功 ⇒ 一补一扣且 affected=0；失败 ⇒ 零流水、预约不悬空 | PASS |
| C-12 | 并发补充竞态 | PASS |
| E-3 | teacher 角色按非 admin 处理（仅本人卡） | PASS |

备注：C-9 参数非法实际为 **422**（FastAPI 全局 `RequestValidationError` handler 既有约定，`error_handler.py:82` 不覆盖；既有测试同约定），与 acceptance 原文 400 差异已在测试文件头注明，登记为文档差异，不改全局 handler（超白名单）。

## 2. 定向回归（分批执行，规避 D-F6.5-6 会话级 fixture 债务）

| 套件 | 结果 |
|------|------|
| `tests/integration/test_card_recommendation.py`（F6.6） | 9 passed |
| `tests/integration/test_booking_reschedule.py`（F6.5） | 31 passed |

## 3. 前端构建验证

| 端 | 命令 | 结果 |
|----|------|------|
| admin-web | `pnpm build`（vue-tsc -b + vite） | PASS（4.12s） |
| miniapp | `pnpm type-check` + `pnpm build:mp-weixin` | 0 error / Build complete |

## 4. 顺带验证结论

- R-5 关闭：C-11 验证旧卡作废后 `restore_credit` 回补路径无双扣（一补一扣，账务守恒）。

## 5. NOT VERIFIED（不得视为 PASS）

- 全量 `pytest`；生产多实例；浏览器/真机交互（转 Stage 11 人工验收）；
- miniapp 前端 join 口径（display_status 1/3 + 卡失效 2/3/6）为前端近似口径，极端数据下以后端 K1 口径为准（前端已限缩，已完成预约不渲染警示）。

结论：**TESTING PASS**（24 新增 + 40 回归，0 FAIL；1 项 400/422 文档差异已登记）。
