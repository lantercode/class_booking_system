# F6.4 需求：预约跨排期时间段重叠校验（D10）

> 来源：`docs/features/F6.0-membership-card-prototype/D10-booking-time-conflict-validation.md`（立项）与 `docs/delivery/feature-backlog.md` F6.4 条目。
> 原型演示态：`docs/features/F6.0-membership-card-prototype/prototype/index.html` → `scheduleTimeConflict`（L814-833）、`submitBooking` 拦截（L1884-1886）。

## 1. 背景

学员当前可以同时预约**时间互相重叠的不同课程**：已约 10-10 19:00–20:30，仍可预约 10-10 19:30–20:30 的另一门课。现有 `create_booking` 只有四类校验：

1. 同排期重复预约（`find_active_booking` + 部分唯一索引）
2. 容量（`booked_count >= capacity`）
3. 时间窗口（已开始 / 超两周 / 未开放 / 已截止）
4. 会员卡有效期重叠（D9，卡维度）

均不覆盖「同一学员在不同排期之间的时间段重叠」。

## 2. 目标

在 `BookingService.create_booking` 中新增一道校验：

> 同一学员的**进行中预约**（`BOOKED` / `CHECKED_IN`）所在排期时间段，与**目标排期时间段**重叠时拒绝本次预约。

判定口径：半开区间 `existing.start_at < target.end_at AND existing.end_at > target.start_at`；边界相接（`end == start`）**不算冲突**。

## 3. 已确认决策（2026-10-22）

| # | 决策项 | 结论 |
|---|--------|------|
| O1 | 是否覆盖式改约（自动取消旧约） | **否**，直接拒绝；改约能力归 F6.5 |
| O2 | 同一课程不同排期是否豁免 | **不豁免**，仍按时间轴判定 |
| O3 | `CHECKED_IN` 是否参与 | **参与**（尚未结束） |
| O4 | `COMPLETED` / `NO_SHOW` / `CANCELLED` 是否参与 | **排除**（已结束/已失效） |
| O5 | 错误文案 | **带课程名与时间段**，例：「该时间段与您已约课程《拉丁舞基础》（10-25 19:00-20:30）冲突，无法预约」 |

## 4. 范围

- `BookingRepository` 新增 1 个区间重叠查询方法 + 1 个学员维度串行化锁方法。
- `BookingService.create_booking` 在同排期查重、会员卡校验之后、容量落库之前插入冲突校验（保证 D9 卡冲突优先提示）。
- 新增集成测试（T1–T8）。
- 4 端影响确认（无契约变更）。

## 5. 非目标

- 不改 D9 会员卡有效期重叠逻辑。
- 不改排期创建时的教室/教师冲突（`ScheduleRepository.find_conflicts` 用途不变）。
- 不新增端点 / DTO / 路由；不做自动取消旧约；不做批量改期。
- 不改前端代码（既有错误信封可直接展示 `msg`）。

## 6. 真实代码对账（spec vs code）

| # | 事实 | 证据 |
|---|------|------|
| C1 | `create_booking` 仅有同排期查重，无跨排期查询 | `booking/service.py:92-94` |
| C2 | `find_active_booking` 仅按 `schedule_id + student_id` 过滤，状态含 `COMPLETED` | `booking/repository.py:123-151` |
| C3 | 已有标准区间范式 `start < :end AND end > :start` | `schedule/repository.py:142-146` |
| C4 | `CourseSchedule.start_at/end_at` 均为 `DateTime(timezone=True)` | `schedule/models.py:42-43` |
| C5 | `create_booking` 运行在默认隔离级别（READ COMMITTED），无 SSI 兜底 | `booking/service.py:56-212`（无 `isolation_level`）；SERIALIZABLE 仅用于排期创建 `schedule/service.py:117-182` |
| C6 | 新增 F6.3 的会员卡校验是**无锁快路径读**，不产生写入 | `booking/service.py:96-116` |
| C7 | 事务内已有 `increment_booked_count`（UPDATE 排期行）与预约插入 | `booking/service.py:118-140` |
| C8 | 错误信封由 `BusinessException(code=400)` 统一返回 | `booking/service.py:73-90` 同类用法 |

> C5 是本次关键对账结论：D10 文档 §6.4 建议「若入口已在 SERIALIZABLE 则依赖 SSI，否则串行化或接受最终一致」。真实代码**未**运行在 SERIALIZABLE，故必须显式串行化，不能依赖 SSI。

## 7. Conflict（文档 vs 真实代码）

| Conflict | Evidence | Impact | Recommendation |
|----------|----------|--------|----------------|
| D10 文档 §6.2 建议校验插在同排期查重后（约原 L89） | 该位置在会员卡校验**之前**；原型约定「卡冲突优先提示」 | 两者同时命中时文案优先级与原型不一致 | 插在会员卡校验之后、`increment_booked_count` 之前，保持无副作用且不改变既有错误优先级 |
| D10 §6.4 认为可由 SERIALIZABLE/SSI 兜底 | `create_booking` 实际为 READ COMMITTED（C5） | 并发重叠预约可能双成功 | 采用学员维度事务级 advisory lock 显式串行化，仅覆盖预约创建路径 |
| 原型文案用字符串字典序比较时间 | `index.html:817-818` | naive 比较在跨时区下错误 | 后端统一用带时区 `datetime` 比较（C4） |

## 8. UNKNOWN

| # | 项 | 处理 |
|---|----|------|
| U1 | 生产环境是否存在合法的「同时间两个不同课程」业务场景（如线上课） | 当前无该业务形态；按 O1 直接拒绝，后续若出现另立 Feature |
| U2 | 员工代约（`source=admin/teacher`）是否也应受此限制 | 本次对**所有来源**生效（同一学员物理时间冲突与来源无关）；如需豁免另议 |
| U3 | 文案中时间段的展示时区 | 后端按 `Asia/Shanghai` 输出（部署区域），记录为已知限制 |
| U4 | 学员维度 advisory lock 与取消/完成链路是否存在死锁 | 通过并发用例验证；完成链路不获取该锁，理论无环，仍需实测 |
