# F4.4 — 核心表 status 字段 Check 约束 · 实施方案

> Feature ID：F4.4
> 作者：database-engineer
> 日期：2026-10-02
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

三张核心表（`bookings` / `course_schedules` / `membership_cards`）的 `status` 字段当前：

1. **模型无 status CheckConstraint**：`Booking.__table_args__` 仅 3 个 Index（含 `uq_bookings_schedule_student_active`）；`CourseSchedule.__table_args__` 已有 `chk_schedule_time` / `chk_schedule_capacity` 但无 status；`MembershipCard.__table_args__` 已有 `chk_credits_range` 但无 status。
2. **DB 无 status Check 约束**：实测 `pg_constraint contype='c'`：bookings 0 个；course_schedules 仅 2 个（非 status）；membership_cards 仅 2 个（非 status）。
3. **枚举值与 backlog 一致**：`BookingStatus {1,2,3,4,5}` / `ScheduleStatus {1,2,3}` / `CardStatus {0,1,2,3,6}`，且 DB 当前无越界行（dev 库）。

直接 `ADD CONSTRAINT` 在 dev 库当前可成功（无越界），但生产不可知 → migration 必须先做 fail-fast 校验再建约束（与 F4.1/F4.2 同范式但策略差异：status 非法值无语义安全的自动修正目标，故不采用防御性清理，而是显式抛错回滚）。

## 已核查的代码与 DB 事实（Evidence）

| 事实 | 证据 |
|------|------|
| 模型当前无 status CheckConstraint | [booking/models.py:66-76](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L66-L76)、[schedule/models.py:65-75](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/models.py#L65-L75)、[membership/models.py:227-239](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L227-L239) |
| DB 无 status Check 约束 | 实测 `pg_constraint` for 三张表：见 requirement.md 表格 |
| DB 无越界 status | 实测 `GROUP BY status`：bookings `{2:3, 5:8}`（11 行）；course_schedules `{2:2, 3:31}`（33 行）；membership_cards `{0:2, 1:6, 2:4, 3:1, 6:4}`（17 行）；全部合法 |
| 枚举值与 backlog 一致 | 模型枚举定义逐一核对，与 backlog T4.4.1/T4.4.2/T4.4.3 无差异 |
| 当前 alembic head | 实测 `alembic_version = f42cd3e4f5a6`（F4.2 后唯一 head） |
| Service 状态机赋值均用枚举 `.value` | grep 三张表对应 Service：status 赋值点均来自枚举（如 `BookingStatus.BOOKED.value`、`ScheduleStatus.NORMAL.value`、`CardStatus.ACTIVE.value`）→ 加约束不破坏既有写入路径 |

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/alembic/versions/f44ab1c2d3e4_add_status_check_constraints.py` | 新建 migration：`revision=f44ab1c2d3e4` / `down_revision=f42cd3e4f5a6`；upgrade=越界校验+3 个 `create_check_constraint`；downgrade=3 个 `drop_constraint` |
| 2 | `apps/api/src/app/modules/booking/models.py` | `__table_args__` 补 `CheckConstraint("status IN (1, 2, 3, 4, 5)", name="ck_bookings_status")`；import 补 `CheckConstraint` |
| 3 | `apps/api/src/app/modules/schedule/models.py` | `__table_args__` 补 `CheckConstraint("status IN (1, 2, 3)", name="ck_course_schedules_status")` |
| 4 | `apps/api/src/app/modules/membership/models.py` | `__table_args__` 补 `CheckConstraint("status IN (0, 1, 2, 3, 6)", name="ck_membership_cards_status")` |
| 5 | `apps/api/tests/integration/test_status_check_constraints.py` | 新建，18 用例覆盖 AC-1~AC-10 |

**不在改动范围**：Service / Repository / Router / schemas / OpenAPI / 前端 / MCP / Redis / payment service。

## Exact Fix

### migration（`f44ab1c2d3e4_add_status_check_constraints.py`）

```python
SPECS = (
    ("bookings", "ck_bookings_status", (1, 2, 3, 4, 5)),
    ("course_schedules", "ck_course_schedules_status", (1, 2, 3)),
    ("membership_cards", "ck_membership_cards_status", (0, 1, 2, 3, 6)),
)

def upgrade():
    # 1. 越界 fail-fast 校验
    for table, _name, values in SPECS:
        rows = conn.execute(text(f"SELECT status, COUNT(*) ... WHERE status NOT IN ({values}) ...")).all()
        if rows: raise RuntimeError(f"F4.4 status Check 约束升级中止...")
    # 2. 加 Check 约束
    for table, name, values in SPECS:
        op.create_check_constraint(name, table, f"status IN ({values})")

def downgrade():
    for table, name, _values in reversed(SPECS):
        op.drop_constraint(name, table, type_="check")
```

### 模型对齐

**booking/models.py**（import 补 `CheckConstraint`）：
```python
__table_args__ = (
    CheckConstraint("status IN (1, 2, 3, 4, 5)", name="ck_bookings_status"),
    Index(...),
    ...
)
```

**schedule/models.py**：
```python
__table_args__ = (
    CheckConstraint("status IN (1, 2, 3)", name="ck_course_schedules_status"),
    CheckConstraint("end_at > start_at", name="chk_schedule_time"),
    ...
)
```

**membership/models.py**：
```python
__table_args__ = (
    CheckConstraint("status IN (0, 1, 2, 3, 6)", name="ck_membership_cards_status"),
    Index(...),
    ...
)
```

## 关键决策记录（Decision）

| # | 决策 | 理由 |
|---|------|------|
| D1 | 越界校验 + 建约束在同一 migration、同一事务 | alembic `Will assume transactional DDL` → 校验失败则 raise RuntimeError，整批回滚；三表约束不加，DB 维持原状，不会出现"加了部分约束但数据不干净"的中间态 |
| D2 | 越界校验采用 fail-fast（抛错回滚），而非防御性清理置 NULL | 非法 status 没有语义安全的自动修正目标（不同于 F4.1/F4.2 的 FK 孤立可安全置 NULL）；静默 UPDATE 会掩盖数据问题；报错打印明细利于人工核查 |
| D3 | 约束名显式 `ck_表名_status`（与模型 `CheckConstraint` 同名） | 便于 downgrade 精确 drop；避免 PG 自动命名（`bookings_status_check`）在不同环境不一致；模型与 DB 一致便于 autogenerate |
| D4 | 模型 `__table_args__` 补同名 `CheckConstraint` | 使模型与 DB 一致；避免 `alembic autogenerate` 误报 diff；ORM 在 flush 时也能提前反映约束语义 |
| D5 | 合法值集合来自 ORM 枚举定义（与 backlog 一致） | 数据库约束是枚举子集的物理实现；枚举定义是事实源；逐一比对 backlog T4.4.1/4.4.2/4.4.3 与模型枚举无差异 |
| D6 | downgrade 顺序：与 upgrade 反序（membership → schedules → bookings） | 安全可审计；Check 约束间无依赖关系，反序仅为规范；不恢复数据（Check 约束不修改存量数据） |
| D7 | 不做成 autogenerate（手动编写 migration） | 显式约束命名 + 越界校验逻辑无法在 autogenerate 中自动生成；手动 migration 更可控 |
| D8 | 不加 `NOT NULL` 约束（status 本身已是 `nullable=False`） | 三张表模型 `status` 列均为 `SmallInteger, nullable=False`，NOT NULL 已满足；仅补取值范围 Check |
| D9 | 不改 Service/Repository | Check 约束在 DB 层，对业务层透明；Service 状态机已正确使用枚举，加约束是纵深防御 |
| D10 | 不扩大范围到其他 status 表（users/courses/orders/classrooms 等） | backlog 仅要求三表；"不为不存在的需求增加数据库结构"；其余表未来有需求时另立 Feature |

## Dependency Analysis

- 复用：既有三表及其 `status` 列；既有种子租户/用户/课程。
- 前置 Feature：F4.2 提供 `down_revision=f42cd3e4f5a6` 链接点。
- 无新外部依赖；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 生产存在越界 status，upgrade 抛错中止 | 中 | fail-fast 打印明细，人工修正后重跑；dev 库已验证 0 越界 |
| 业务层现有代码写非法 status（如硬编码数字） | 低 | grep Service 层状态赋值点均用枚举 `.value`；无硬编码非法值 |
| 排期 booking 依赖 booking 的 status 做部分唯一索引（`uq_bookings_schedule_student_active` 限定 `status IN (1,3,4)`） | 低 | Check 约束合法集合 `(1,2,3,4,5)` 包含唯一索引子集 `(1,3,4)`，无冲突 |
| migration revision 链断裂 | 低 | `down_revision=f42cd3e4f5a6`（实测唯一 head）；`alembic heads` 验证单 head |
| F4.1/F4.2 回归 | 低 | bookings/orders 的 FK + 索引未动；仅新增 status Check |

## Implementation Steps

1. 写 migration `f44ab1c2d3e4_*.py` → py_compile。
2. `alembic upgrade head` 应用 → 验证越界=0 + 三约束存在。
3. `alembic downgrade -1` + `alembic upgrade head` 验证可逆。
4. 改三张模型补 `CheckConstraint` → py_compile。
5. 写 `test_status_check_constraints.py`（18 用例）→ 迭代至全绿。
6. 静态审查 diff（仅 migration + 3 模型 + 新测试）。
7. 回归 `test_booking_fk_membership_card.py`（F4.1）+ `test_order_fk_membership_card.py`（F4.2）。

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1~3 | `test_check_constraint_exists`（parametrized，3 用例） |
| AC-4 | `test_booking_invalid_status_rejected[0/6/99]`（3 用例） |
| AC-5 | `test_schedule_invalid_status_rejected[0/4/99]`（3 用例） |
| AC-6 | `test_card_invalid_status_rejected[4/5/99]`（3 用例） |
| AC-7 | `test_booking_valid_statuses_succeed`（1 用例） |
| AC-8 | `test_schedule_valid_statuses_succeed`（1 用例） |
| AC-9 | `test_card_valid_statuses_succeed`（1 用例） |
| AC-10 | `test_no_out_of_range_status_and_data_present[bookings/schedules/cards]`（3 用例） |
| AC-11 | 回归 F4.1 + F4.2 |
| AC-12 | 静态 grep：Service/Repository 零改动、模型与 migration 一致 |
| AC-13 | `alembic downgrade -1` + `alembic upgrade head` 往返 |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 生产库是否存在越界 status 行 | dev 库 0 越界；生产不可知 → fail-fast 抛错回滚并打印明细，人工修正后重跑 |
| U2 | 是否有后台脚本/修复工具绕过 Service 写非法 status | grep 未命中；若存在此类脚本，Check 约束将拦截其非法写入，即约束本身即目的 |
| U3 | `membership_cards` 既有 Check 命名漂移（模型 `chk_credits_range` vs DB `chk_used_credits_valid`/`chk_total_credits_positive`） | 存量历史差异；不影响本 Feature；未来需 autogenerate 对齐时可另立 Feature |
