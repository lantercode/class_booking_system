# F6.7 静态验证报告

> 日期：2026-10-22。范围：白名单 10 文件（见 implementation-report §1）。

| # | 项 | 命令 / 方式 | 结果 |
|---|----|------------|------|
| A-1 | Python 语法 | `.venv/bin/python -m py_compile` ×5 改动文件（每改一文件即执行） | PASS |
| A-2 | 后端 lint | `.venv/bin/ruff check` ×5 改动文件 | PASS（0 error） |
| A-3 | 端点注册 | `membership/router.py` L292-319，路径 `/cards/{card_id}/affected-bookings` 无尾斜杠，无 `@require_roles`，`redis_client` DI 存在 | PASS |
| A-4 | OpenAPI 契约 | `pnpm gen:types` 重新生成（82 路径），新端点在 `openapi.json` / `schema.d.ts` 存在，无手改 | PASS |
| A-5 | 前端路由核对 | affected-bookings / reschedule / recommend-card / my-cards / tenant-info 逐一核对后端真实存在 | PASS |
| A-6 | admin-web 类型+构建 | `pnpm build`（vue-tsc -b + vite build） | PASS（4.12s） |
| A-7 | miniapp 类型+构建 | `pnpm type-check`（0 error）+ `pnpm build:mp-weixin` | PASS（Build complete） |
| A-8 | 分层审查 | 端点无业务判断；归属校验在 BookingService；Repository 显式 tenant_id；无跨模块 Repository 直调；无循环 import（booking/service.py 持有 membership 单例方向不变） | PASS |
| A-9 | 事务边界 | 新增链路纯只读（无 commit/flush/FOR UPDATE）；freeze/cancel/reschedule/create_booking 事务路径零改动 | PASS |
| A-10 | 生成物完整性 | `packages/api-types` 仅 `pnpm gen:types` 产物 | PASS |

结论：**STATIC PASS**（无 FAIL 项；C-9 的 400/422 差异属运行时约定，见 runtime-test-report 备注）。
