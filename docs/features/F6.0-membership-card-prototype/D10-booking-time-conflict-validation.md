# D10 学员约课「跨排期时间段重叠」校验（立项文档）

> 本文件是 F6.0 缺口登记项 D10 的正式立项文档。**已由 F6.4 落地（2026-10-22），后端实现见 `docs/features/F6.4-booking-time-overlap/`。**

## 1. 立项信息

| 项 | 内容 |
|----|------|
| 编号 | D10 |
| 名称 | 学员约课跨排期时间段重叠校验 |
| 状态 | **已实现**（F6.4，2026-10-22，后端验收通过） |
| 提出日期 | 2026-10-19 |
| 来源 | F6.0 原型核查（核查发现真实后端 `create_booking` 缺跨排期时间段重叠校验） |
| 关联原型演示态 | `prototype/index.html` 的 `scheduleTimeConflict`（L814-833）与 `submitBooking` 拦截（L1884-1886）；演示排期 `S6`（L632-633） |
| 关联验证 | `verify-prototype.js` [L] 组（L338-363，7 条） |
| 决策登记 | `open-decisions.md` → D10 |

## 2. 背景与问题

**现状**：学员可以预约到**时间上互相重叠的不同课程**。例如已约 10-10 19:00–20:30 的课，仍可再约 10-10 19:30–20:30 的另一门课，两者到店时间必然冲突。

**现有校验（`create_booking` 内）只覆盖 4 类**，均不涉及跨排期时间段：

1. **同排期重复预约**：`find_active_booking` + 部分唯一索引，只判断"同一 schedule_id + 同一 student_id"；
2. **容量**：`booked_count >= capacity` 拒绝；
3. **时间窗口**：课程已开始 / 超过未来两周 / 未开放 / 已截止；
4. **会员卡有效期重叠**（D9）：按卡的**有效期区间**判定，维度是"卡"而非"排期时间轴"，见 `booking/service.py:130-155`。

> 注意：第 4 类与本次缺口**必须解耦**——D9 判的是"同一课程类型的卡有效期是否有交集"，本次 D10 判的是"同一学员的排期时间段是否重叠"，两者口径、对象、数据源均不同。

## 3. 缺口证据（文件:行号）

| # | 证据 | 说明 |
|---|------|------|
| E1 | `apps/api/src/app/modules/booking/service.py:87-89` | `create_booking` 仅有 `repo.find_active_booking(db, schedule_id, student_id)` 同排期查重，之后直接进入扣次/落库；**无任何跨排期查询**。 |
| E2 | `apps/api/src/app/modules/booking/repository.py:123-151` | `find_active_booking` 的查询谓词只含 `Booking.schedule_id == schedule_id AND Booking.student_id == student_id`，未 JOIN 排期时间，无法表达"时间段重叠"。 |
| E3 | `apps/api/src/app/modules/booking/models.py:66-79` | `uq_bookings_schedule_student_active`（L71-77）是**按 (schedule_id, student_id)** 的部分唯一索引（`status IN (1,3,4)`），只防同排期重复；现有 `idx_bookings_student`（L78）为 `(tenant_id, student_id, status)`。 |
| E4 | `apps/api/src/app/modules/schedule/repository.py:103-146` | `find_conflicts` 已具备标准区间重叠范式 `start_at < :end_at AND end_at > :start_at`（L144-145），但该方法**只服务于排期创建时的教室/教师冲突**（`classroom_id` / `teacher_id`，L158-163），与学员维度无关。 |
| E5 | `apps/api/src/app/modules/schedule/models.py:42-43` | `CourseSchedule.start_at` / `end_at` 均为 `DateTime(timezone=True)`（带时区），为跨排期区间比较提供了统一时间轴。 |
| E6 | `apps/api/src/app/modules/booking/service.py:130-155` | 会员卡有效期重叠（D9）走的是 `membership_card_service.deduct_credit`，是**卡维度**的另一校验，不覆盖排期时间轴重叠。 |

## 4. 目标 / 范围

**目标**：在 Service 层 `create_booking` 中新增一道校验——

> **同一学员**的**进行中预约**（`BOOKED` / `CHECKED_IN`）**所在排期的时间段**与**目标排期时间段**重叠时，拒绝本次预约。

**范围**：

- 仅后端 `booking` 模块 Service / Repository 层新增校验逻辑（预计新增 1 个 Repository 方法 + 1 段 Service 校验）。
- 判定对象：学员维度的预约记录（通过 `Booking.student_id` 关联 `CourseSchedule` 的时间字段）。
- 时间比较口径：半开区间 `a.start < b.end AND b.start < a.end`；**边界相接（`a.end == b.start`）不算冲突**。
- 属确定性待开发项，无产品方案分歧。

## 5. 非目标（明确不做）

- **不改**会员卡有效期重叠逻辑（D9 `cardConflict` / `deduct_credit` 内校验保持不变）。
- **不涉及**排期创建时的教室/教师冲突（`find_conflicts` 用途不变）。
- **不做前端大改**：原型演示态（`scheduleTimeConflict` + `submitBooking` 拦截）已具备，前端仅需展示既有错误文案。
- 不新增独立端点、不改路由与请求/响应 DTO。

## 6. 技术方案建议

### 6.1 新增 Repository 方法

在 `BookingRepository`（已继承 `TenantAwareRepository[Booking]`，自动租户隔离）新增：

```python
async def find_overlapping_active_booking(
    self, db: AsyncSession, *, student_id: int, start_at: datetime, end_at: datetime
) -> Booking | None:
    """查找该学员进行中预约中，所在排期时间段与 [start_at, end_at) 重叠的预约"""
```

**查询范式**（复刻 `schedule/repository.py:144-145` 的既有口径）：

```
JOIN course_schedules s ON bookings.schedule_id = s.id
WHERE bookings.student_id = :student_id
  AND bookings.status IN (BOOKED, CHECKED_IN)
  AND s.start_at < :end_at
  AND s.end_at   > :start_at
```

- **半开区间**：`s.start_at < :end_at AND s.end_at > :start_at`，边界相接（`s.end_at == :start_at` 或 `s.start_at == :end_at`）**不算冲突**。
- **状态过滤**：采用 `status ∈ {BOOKED, CHECKED_IN}`（进行中）。是否纳入 `COMPLETED` 见「待确认项」（默认排除）。
- **租户隔离**：Repository 继承 `TenantAwareRepository`，租户条件由 ContextVar / ORM 事件自动注入；如需显式叠加与现有 `find_active_booking` 保持同构（`get_tenant_id()`），但**禁止绕过**（见 `security/tenant-isolation.md`）。
- **只返回 1 条即可**（冲突存在性判断 + 用于错误文案显示冲突课程名）；必要时可 `limit(1)`。

### 6.2 调用点

在 `create_booking` 的**同排期查重之后、扣次之前**插入（约 L89 之后）：

```python
conflict = await self.repo.find_overlapping_active_booking(
    db, student_id=student_id, start_at=schedule.start_at, end_at=schedule.end_at
)
if conflict:
    raise BusinessException("该时间段与您已约课程冲突，无法预约", code=400)
```

（如需错误文案带冲突课程名，可复用 `_get_schedule_info_map`（`booking/service.py:477-521`）取 `course_name`。）

### 6.3 索引建议

- Booking 侧：现有 `idx_bookings_student` = `(tenant_id, student_id, status)`（`booking/models.py:78`）**已可支撑**学员维度过滤，通常无需新增索引。
- Schedule 侧：现有 `idx_schedules_tenant_start` = `(tenant_id, start_at)`（`schedule/models.py:75`）可支撑区间扫描；如需更优可评估 `(tenant_id, start_at, end_at)`。**建议先复用现有索引，避免过早新增**。

### 6.4 事务 / 并发

- 该校验发生在与 `create_booking` 相同的 `AsyncSession` 事务内，命中即 throw → 整个事务回滚（与现有容量/时间窗口校验同语义）。
- **并发取舍**：区间重叠无法用唯一索引直接兜底，`find_conflicts` 注释（`schedule/repository.py:120-132`）也指出 SERIALIZABLE 下由 SSI 谓词锁兜底。建议：
  - 若预约入口已运行在 `SERIALIZABLE`（或 `REPEATABLE READ` + 相应锁策略），则普通快照谓词读配合 SSI 即可检测并发插入冲突；
  - 否则在 Service 层对"该学员进行中预约集合"做必要的串行化（如对学员维度加锁或接受最终一致），**不得**在 Repository 层发明绕过事务的写法（见 `ai/mcp.md` 写操作条款）。

### 6.5 错误语义与文案示例

- 抛 `BusinessException(..., code=400)`，与现有同类业务错误一致。
- 文案示例（对齐原型 `index.html:1886`）：
  - 简洁版：「该时间段与您已约课程冲突，无法预约」
  - 带上下文版：「该时间段与您已约课程《拉丁舞基础》冲突（19:30-20:30 与 19:00-20:30），无法预约」
- 不向前端回传内部异常 / SQL / 堆栈。

## 7. 接口与契约影响（4 端显式评估）

| 端 | 是否涉及 | 结论 |
|----|----------|------|
| **admin-web** | 否 | 不新增/修改任何端点与 DTO；管理端不参与该拒绝路径的交互变更。结论：**不涉及**。 |
| **student-web** | 是（弱） | 不新增端点，仅业务错误语义增强——学员预约被拒时返回既有信封错误（`code != 0` + 400）。现有错误处理链路可直接展示 `msg`，**无需新增字段**。结论：**涉及文案展示，无契约变更**。 |
| **teacher-web** | 否 | 不涉及教师端接口与交互。结论：**不涉及**。 |
| **miniapp（学员/教师）** | 是（弱） | 同 student-web：调用 `POST /api/v1/bookings`（既有端点）时可能多收到一类 400 业务错误；`apps/miniapp/src/api/index.ts` 统一错误处理可覆盖，**无契约变更**。结论：**涉及文案展示，无契约变更**。 |

> 结论：**无破坏性契约变更**（不新增字段、不改类型、不改路由）。仅新增一类业务错误返回，属兼容变更。

## 8. 测试计划

| # | 用例 | 预期 |
|---|------|------|
| T1 | 学员已有进行中预约（BOOKED）于 19:00–20:30，尝试预约同租户另一 19:30–20:30 排期 | 被拦截，400「该时间段与您已约课程冲突」 |
| T2 | 边界相接：已有预约 19:00–20:00，尝试预约 20:00–21:00 | **放行**（半开区间不重叠） |
| T3 | 已有预约状态为 `CANCELLED` / `COMPLETED` / `NO_SHOW` | **不参与判定**，放行 |
| T4 | 已有预约状态为 `CHECKED_IN` 且时间重叠 | 被拦截 |
| T5 | **跨租户隔离**：A 租户学员的时间冲突预约，不阻止 B 租户学员 | 放行（租户隔离生效） |
| T6 | 非重叠排期正常预约 | 成功创建，扣次/流水与现状一致 |
| T7 | 并发：同一学员同时发起两个重叠排期的预约 | 至多一个成功（由 SSI / 序列化兜底），无静默双占 |
| T8 | 回归：同排期重复预约、容量、时间窗口、D9 卡有效期重叠 | 原有行为不回归 |

## 9. 验收标准

- [ ] `create_booking` 在跨排期时间段重叠时稳定返回 400 + 友好文案，且不落库、不扣次。
- [ ] 边界相接（`end == start`）判为**不冲突**，预约成功。
- [ ] `CANCELLED` / `COMPLETED` / `NO_SHOW` 状态的既有预约**不参与**判定。
- [ ] 跨租户不互相干扰（T5 通过）。
- [ ] 租户隔离走 `TenantAwareRepository` / ContextVar，无绕过租户注入的裸查询。
- [ ] 与 D9 卡有效期重叠校验**解耦**，互不覆盖（两者可同时命中，提示按既定优先级）。
- [ ] 无前端契约变更；4 端影响面结论与本文第 7 节一致。
- [ ] 新增 Repository 方法有对应单测/集成测试覆盖（T1–T7）。

## 10. 风险与依赖

| 项 | 说明 |
|----|------|
| **时区一致性** | 依赖 `CourseSchedule.start_at/end_at` 为 `DateTime(timezone=True)`（`schedule/models.py:42-43`）。比较必须在同一时区基准下进行；原型演示态用字符串字典序（`index.html:817-818`），真实后端须用带时区 datetime，禁止 naive/aware 混用。 |
| **性能** | 每单多一次 JOIN 查询；命中现有 `idx_bookings_student` + `idx_schedules_tenant_start`，量级可接受。如需可评估扩展索引 `(tenant_id, start_at, end_at)`。 |
| **并发一致性** | 区间重叠无唯一约束兜底，依赖 SERIALIZABLE / SSI 或序列化策略（见 6.4）。 |
| **与 D9 / 卡冲突的先后顺序** | 需明确：卡有效期冲突与时间段冲突同时命中时的提示优先级。原型约定"命中卡冲突优先提示卡冲突"（`open-decisions.md` D10 解耦说明），后端建议沿用。 |
| **依赖** | `booking`、`schedule` 两模块的 Service/Repository 分层不变；不新增跨模块 Repository 直访（遵循 `architecture/layering.md`）。 |

## 11. 待确认项

1. **是否允许"覆盖式"改约**：学员约到冲突排期时，是否提供"自动取消旧预约并改约"？（原型当前为**直接拒绝**，未见改约入口。）
2. **同一课程不同排期是否豁免**：同一 `course_id` 的不同排期若时间重叠，是否也判冲突？（建议：**不豁免**，仍按时间轴判定。）
3. **判定是否包含 `CHECKED_IN`**：本文默认"进行中"= `BOOKED` / `CHECKED_IN`；需确认 `CHECKED_IN` 是否纳入（建议纳入，因其尚未结束）。
4. **`COMPLETED` 是否参与**：本文默认**排除**（已完成课程不应再阻挡未来预约），需产品确认。
5. **错误文案与是否回带冲突课程名**：使用简洁版还是带上下文版（含课程名/时间段）。

## 12. 关联与后续步骤

**关联**：

- 原型演示态：`prototype/index.html` → `scheduleTimeConflict`（L814-833）、`submitBooking` 拦截（L1884-1886）、演示排期 `S6`（L632-633）。
- 原型验证：`verify-prototype.js` [L] 组（L338-363，7 条断言：L1 确认阶段拦截 / L2 文案 / L3 无副作用 / L4-L5 非冲突放行 / L6-L7 与 D9 解耦）。
- 决策清单：`open-decisions.md` → D10。

**后续实现顺序（建议）**：

1. 确认第 11 节待确认项（产品/技术）。
2. `booking/repository.py` 新增 `find_overlapping_active_booking`（复刻 `schedule/repository.py:144-145` 区间范式）。
3. `booking/service.py::create_booking` 在 L89 后插入校验。
4. 补单测 / 集成测试（T1–T7），跑 `schedule` 与 `booking` 既有测试确认无回归。
5. 更新 OpenAPI 无关（无契约变更）；4 端文案确认。
6. **交付后**再回写本文件状态为"已实现"，并同步 `open-decisions.md`。

---

> **状态声明（2026-10-22 更新）**：本校验已由 **F6.4** 在 `BookingService.create_booking` 落地，交付与验收记录见 `docs/features/F6.4-booking-time-overlap/`。
> 第 11 节 5 项待确认项已按推荐口径确认：直接拒绝（不覆盖式改约）/ 同课程不豁免 / 纳入 `CHECKED_IN` / 排除 `COMPLETED` / 文案带课程名与时间段。
> 实现偏差：校验插入点移至会员卡校验**之后**（保持卡冲突优先提示）；并发兜底改为 `pg_advisory_xact_lock(tenant, student)`（真实入口为 READ COMMITTED，非 SERIALIZABLE）。
