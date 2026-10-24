# F6.4 发布说明

## Feature

预约跨排期时间段重叠校验（D10）：同一学员的进行中预约所在排期时间段与目标排期重叠时拒绝预约。

## Problem

`create_booking` 仅校验同排期重复、容量、时间窗口、会员卡有效期，未校验**跨排期时间轴重叠**，学员可同时预约 19:00–20:00 与 19:30–20:30 的两门课。

## Fix

- `BookingRepository.find_overlapping_active_booking`：JOIN 排期，半开区间重叠查询，仅 `BOOKED/CHECKED_IN`，按租户过滤。
- `BookingRepository.lock_student_booking_scope`：同一租户同一学员的预约创建串行化（事务级 advisory lock），解决 READ COMMITTED 下并发双占。
- `BookingService.create_booking`：卡校验后、占名额前插入校验；命中返回 400，文案含课程名与时间段。
- `BookingService._format_time_conflict_message`：UTC → `Asia/Shanghai` 展示。

## Files Changed

- `apps/api/src/app/modules/booking/repository.py`
- `apps/api/src/app/modules/booking/service.py`
- `apps/api/tests/integration/test_booking_time_overlap.py`（新增）

无迁移、无配置项、无路由/DTO 变更。

## Tests

| 集合 | 结果 |
|------|------|
| F6.4 定向 8 条 | 11 次执行全部通过（含 10 轮稳定性） |
| F6.3 定向 41 条 | PASS |
| 通用回归 118 条 | PASS |

## Acceptance

- B-1 ~ B-6、D-1、D-3、E-1 ~ E-3：PASS
- C-3：Repository 层部分验证
- D-2、全量 pytest、API 级双租户、多实例：NOT VERIFIED

## Known Risks

1. advisory lock 双键 int4，ID 超 2^31 溢出（当前量级安全）
2. 取消/完成链路不取该锁，D-2 未实测
3. 文案时区固定 `Asia/Shanghai`
4. 全量 `pytest` 未执行

## Release Notes

- 兼容变更：不新增字段/端点，仅新增一类 400 业务错误；4 端无需改动。
- 上线后建议观察：预约拒绝率、冲突文案分布、advisory lock 等待时长。
