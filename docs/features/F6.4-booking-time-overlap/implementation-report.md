# F6.4 实施报告

> 日期：2026-10-22
> 范围：`booking` 模块（Repository + Service）+ 1 个集成测试文件
> 结论：实现完成，定向 8 条 + 回归 41 + 118 全部通过；无迁移、无契约变更。

## 1. 落地内容

| 任务 | 实现 |
|------|------|
| T6.4.1 区间重叠查询 | `BookingRepository.find_overlapping_active_booking`：JOIN 排期，半开区间，`BOOKED/CHECKED_IN`，租户显式谓词，`ORDER BY start_at LIMIT 1` |
| T6.4.2 学员维度串行化 | `BookingRepository.lock_student_booking_scope`：`pg_advisory_xact_lock(tenant, student)`，事务级，自动释放 |
| T6.4.3 Service 校验与文案 | `create_booking` 在卡校验后、占名额前插入校验；`_format_time_conflict_message` 输出带课程名与时间段 |
| T6.4.4 测试 | `tests/integration/test_booking_time_overlap.py` 共 8 条 |
| T6.4.5 4 端影响 | 无端点/DTO 变更，前端零改动 |

## 2. 文件级变更

| 文件 | 变更 |
|------|------|
| `apps/api/src/app/modules/booking/repository.py` | `+text` 导入；新增 2 个方法（约 65 行） |
| `apps/api/src/app/modules/booking/service.py` | `+ZoneInfo`、`_DISPLAY_TZ`、冲突校验段（约 20 行）、`_format_time_conflict_message`（约 15 行） |
| `apps/api/tests/integration/test_booking_time_overlap.py` | 新增，8 条用例 |

无数据库迁移、无配置项、无路由/Schema 变更。

## 3. 关键实现细节

- **插入位置**：`create_booking` 的会员卡校验之后、`increment_booked_count` 之前。
  - 理由 1：命中时不占名额、不扣次，事务无副作用；
  - 理由 2：保持「卡冲突优先提示」的原型约定。
- **半开区间**：`CourseSchedule.start_at < end_at AND CourseSchedule.end_at > start_at`，与 `ScheduleRepository.find_conflicts` 同范式。
- **并发**：真实代码为 READ COMMITTED（无 SSI），故用事务级 advisory lock 串行化同一租户同一学员的预约创建；锁在 COMMIT/ROLLBACK 自动释放。
- **文案时区**：库内 UTC，输出转为 `Asia/Shanghai`（已知限制，多区域部署需改租户级配置）。

## 4. 与设计的偏差

| 项 | 设计 | 实现 | 原因 |
|----|------|------|------|
| 校验插入点 | D10 文档建议在同排期查重后 | 放在会员卡校验之后 | 保持卡冲突优先提示（见 Conflict 1） |
| 并发兜底 | D10 文档建议依赖 SSI 或接受最终一致 | 显式 advisory lock | 真实代码非 SERIALIZABLE（见 Conflict 2） |
| 返回结构 | D10 建议返回 Booking | 返回 `Booking`，课程名另查 | 复用现有 `_get_schedule_info_map` |

## 5. 未完成 / NOT VERIFIED

- 全量 `pytest` 未执行（仅定向 + 回归集）
- D-2 并发取消 vs 预约的死锁场景未构造用例
- 生产多实例下 advisory lock 行为未实测（PostgreSQL 集群级锁，理论有效）
- 跨租户 API 级用例仅覆盖 Repository 层（C-3 部分验证）

## 6. 验证入口

- `static-verification.md`
- `runtime-test-report.md`
- `review.md`
