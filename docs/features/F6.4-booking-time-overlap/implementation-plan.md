# F6.4 实施计划：预约跨排期时间段重叠校验

> 设计对象为真实代码（2026-10-22，含 F6.3 已落地改动）。无数据库结构变更、无新增端点、无 DTO 变更。

## 1. 任务拆分

| 任务 | 内容 | 文件 |
|------|------|------|
| T6.4.1 | Repository 新增区间重叠查询 | `booking/repository.py` |
| T6.4.2 | Repository 新增学员维度事务级串行化锁 | `booking/repository.py` |
| T6.4.3 | Service 插入冲突校验 + 错误文案 | `booking/service.py` |
| T6.4.4 | 集成测试 T1–T8 | `tests/integration/test_booking_time_overlap.py`（新增） |
| T6.4.5 | 4 端影响确认（无契约变更） | 本文 §6 |

## 2. T6.4.1 区间重叠查询

```python
async def find_overlapping_active_booking(
    self,
    db: AsyncSession,
    *,
    student_id: int,
    start_at: datetime,
    end_at: datetime,
) -> Booking | None:
```

- JOIN：`Booking.schedule_id == CourseSchedule.id`
- 谓词：`Booking.student_id == :student_id`、`Booking.status IN (BOOKED, CHECKED_IN)`、
  `CourseSchedule.start_at < :end_at`、`CourseSchedule.end_at > :start_at`
- 租户：沿用 `find_active_booking` 的显式 `Booking.tenant_id == get_tenant_id()`（同在 Repository 内），并注释说明原因（JOIN 场景下避免仅依赖自动注入）
- 排序 `CourseSchedule.start_at ASC` + `limit(1)`：命中多条时返回最早一条，用于文案

## 3. T6.4.2 学员维度串行化

```python
async def lock_student_booking_scope(
    self, db: AsyncSession, *, tenant_id: int, student_id: int
) -> None:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(CAST(:tenant_id AS integer), CAST(:student_id AS integer))"),
        {"tenant_id": tenant_id, "student_id": student_id},
    )
```

**理由**：区间重叠无法用唯一索引兜底，`create_booking` 运行在 READ COMMITTED（见 requirement §6 C5），
不依赖 SSI。advisory lock 为事务级，随 COMMIT/ROLLBACK 自动释放，无需显式解锁。

**风险**：
- 双键形式为 `(int4, int4)`，ID 超过 2^31 会溢出（当前 `BIGSERIAL` 量级远低于此，记录为限制）
- 与取消/完成链路的锁序：完成链路不获取该锁，理论无环；由 D-1/D-2 用例实测
- 该锁只串行化**同一租户同一学员**的预约创建，不阻塞其他学员

## 4. T6.4.3 Service 插入点与文案

插入位置：会员卡校验（`booking/service.py:96-116`）之后、`increment_booked_count`（L118）之前。

```python
# F6.4：同一学员跨排期时间段重叠校验（D10）。
# 置于扣次/占名额之前，命中即回滚，不产生副作用；同时保持"卡冲突优先提示"。
await self.repo.lock_student_booking_scope(
    db, tenant_id=schedule.tenant_id, student_id=student_id
)
conflict = await self.repo.find_overlapping_active_booking(
    db, student_id=student_id,
    start_at=schedule.start_at, end_at=schedule.end_at,
)
if conflict:
    info = (await self._get_schedule_info_map(db, [conflict.schedule_id])).get(
        conflict.schedule_id, {}
    )
    raise BusinessException(self._time_conflict_message(info), code=400)
```

文案（`Asia/Shanghai` 展示；记录为已知限制 U3）：

```
该时间段与您已约课程《拉丁舞基础》（10-25 19:00-20:30）冲突，无法预约
```

缺课程名/时间时降级为「该时间段与您已约课程冲突，无法预约」。

## 5. T6.4.4 测试计划

| # | 用例 | 构造 | 预期 |
|---|------|------|------|
| T1 | B-1 重叠拒绝 | 已有 BOOKED 10:00–11:00，目标 10:30–11:30 | 400 + 文案；预约数不变；卡未扣 |
| T2 | B-2 边界相接 | 已有 10:00–11:00，目标 11:00–12:00 | 201 |
| T3 | B-4 终态不参与 | 已有 CANCELLED / COMPLETED / NO_SHOW，目标重叠 | 201 |
| T4 | B-3 CHECKED_IN 参与 | 已有 CHECKED_IN 10:00–11:00，目标 10:30 | 400 |
| T5 | C-3 跨租户 | A 租户已约；B 租户学员同排期时间 | 201（若无第二租户则 NOT VERIFIED） |
| T6 | B-5 非重叠 | 目标 15:00 | 201 |
| T7 | D-1 并发 | 同一学员并发两个重叠排期 | 恰好一个 201、一个 400 |
| T8 | E-1 回归 | 同排期重复预约 / 容量满 | 原错误文案不变 |

测试复用 `tests/membership_support.py` 的夹具；学员登录使用 `SEED_STUDENT`。

## 6. 4 端影响

| 端 | 涉及 | 结论 |
|----|------|------|
| admin-web | 否 | 无端点/DTO 变更，不新增 UI |
| student-web | 弱 | 仅多一类 400 业务错误，既有 `msg` 展示链路覆盖 |
| teacher-web | 否 | 不涉及 |
| miniapp | 弱 | 同 student-web；`api/index.ts` 统一错误处理覆盖 |

**无破坏性契约变更**。

## 7. 验证命令

```bash
cd apps/api
python3 -m py_compile src/app/modules/booking/repository.py src/app/modules/booking/service.py
.venv/bin/ruff check src/app/modules/booking tests/integration/test_booking_time_overlap.py
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_time_overlap.py -q
```

## 8. 回滚方案

代码回滚即可（无迁移、无配置项）。已产生的数据无结构变化。

## 9. UNKNOWN / 待验证

| # | 项 | 验证方式 |
|---|----|----------|
| U1 | advisory lock 双键 int4 溢出 | 代码审查 + 记录限制 |
| U2 | 与取消/完成链路死锁 | D-2 用例 / 未覆盖则 NOT VERIFIED |
| U3 | 文案时区固定 `Asia/Shanghai` | 记录为已知限制 |
| U4 | 生产多实例下 advisory lock 有效性 | PostgreSQL 集群级锁，理论有效；未做多实例实测 |
