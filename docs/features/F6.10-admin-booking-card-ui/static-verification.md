# F6.10 静态验证

## 构建与类型检查

| 命令 | 结果 |
|------|------|
| `pnpm --filter admin-web build`（含 vue-tsc -b） | ✅ 通过，built in 7.29s |
| `pnpm --filter teacher-web build`（含 vue-tsc -b） | ✅ 通过，built in 4.39s |
| `python -m py_compile` booking/service/router/schemas | ✅ 通过 |
| `pytest tests/integration -k "booking and (list or cancel or check)"` | ✅ 17 passed |
| `packages/api-client/src/bookings.ts` 类型 | ✅ 由 admin-web/teacher-web vue-tsc 覆盖（该包无独立 build script） |

仅有与本改动无关的预存警告（chunk size > 500kB、api-client re-export 循环依赖 chunk 警告）。
`test_insufficient_credits_rolls_back_booking_and_capacity` 单次偶发失败（时间段冲突，重跑通过），与本次改动无关。

## 契约对齐（A-6）

- `Booking` 字段与 `apps/api/src/app/modules/booking/schemas.py` `BookingResponse` 对齐：`course_name/start_at/end_at/classroom_name/teacher_name/display_status` 均为后端已有返回字段。
- `bookingApi.list` 参数 `status` 字符串逗号拼接与后端 `router.py:55-100` 解析逻辑一致。
- `membershipCardApi.getTransactions` 调用 `GET /membership/transactions?card_id=`，与后端 `router.py:538-559` 一致。

## 分层合规（A-7）

- 未改后端、未改 DB、未改 api-types。
- 前端只通过 `@dance-saas/api-client` 访问后端，未新增第三套请求层。
- 未触碰 `student-web` / `miniapp`。

## 四态完整性

- 预约管理页：loading（el-table v-loading）、empty（empty-text）、error（el-result 重试）、data ✅
- 卡流水区块：loading（skeleton）、empty（暂无流水）、error（el-result 重试）、data ✅
- 教师端完成按钮：仅 attended 状态显示，completed 后隐藏 ✅

## 安全

- 签到/完成端点后端要求 `booking:manage`，前端不绕过；列表端点 Service 层角色分流。
- 错误提示取 `e?.response?.data?.msg`，不暴露堆栈。
- 卡详情流水按 `card_id` 过滤，租户隔离由后端保证。
