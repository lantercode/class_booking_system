# F6.5 实施报告：原子改期 / 原子改派

> 日期：2026-10-22
> 范围：`booking`（模型/Repository/Service/DTO/路由）+ `schedule`（排期锁）+ `membership`（卡集锁）+ 迁移 + 2 个集成测试文件
> 结论：T6.5.1 ~ T6.5.11 全部落地；定向 31 + 并发 9（含 D-6 两条）通过；定向回归 93（分两批，含 RBAC 17）通过；迁移可 `upgrade/downgrade` 往返。

## 1. 任务落地

| 任务 | 实现 |
|------|------|
| T6.5.1 模型 + 迁移 | `BookingReschedule`（`booking/models.py:93`）；`alembic/versions/f6a5b4c3d2e1_add_booking_reschedules.py`（down_revision `a7b8c9d0e1f2`）；含 `tenant_id -> tenants.id ON DELETE CASCADE`、CHECK、2 个部分唯一索引、2 个普通索引 |
| T6.5.2 Repository | `find_active_booking` / `find_overlapping_active_booking` 增加 `exclude_booking_id`（`booking/repository.py:123`、`:184`）；`get_by_id_for_update` 追加 `populate_existing=True`（`:281`）；新增 `BookingRescheduleRepository`（`:422`） |
| T6.5.3 排期锁 | `ScheduleRepository.get_by_ids_for_update`（`schedule/repository.py:182`，去重 + id ASC + `FOR UPDATE` + `populate_existing`）；`ScheduleService.get_schedules_for_update`（`schedule/service.py:552`，缺失即 404） |
| T6.5.4 卡集锁 | `MembershipCardService.lock_student_cards_for_booking_change`（`membership/service.py:659`，覆盖 PENDING/ACTIVE/EXPIRED/FROZEN/CANCELLED） |
| T6.5.5 复合事务 | `BookingService.reschedule_booking`（`booking/service.py:344`）+ 8 个私有辅助（`:628` ~ `:874`）；取消窗口抽取为 `_assert_cancel_window`（`:686`），`_do_cancel_booking` 同步复用 |
| T6.5.6 DTO / 路由 | `BookingRescheduleRequest`（`schemas.py:20`）、`BookingRescheduleResponse`（`:72`）；`POST /bookings/{booking_id}/reschedule`（`router.py:184`） |
| T6.5.7 OpenAPI / 类型 | 重新生成 `packages/api-types/openapi.json`、`schema.d.ts`，未手改 |
| T6.5.8 测试 | `tests/integration/test_booking_reschedule.py`（28 函数 / 31 例）、`test_booking_reschedule_concurrency.py`（9 例，含 D-6 两条）；`tests/membership_support.py` 扩展 `create_student` 与审计表清理 |
| T6.5.11 排期取消锁硬化 | `ScheduleService.cancel_schedule` 改为 `booking(id ASC) → schedule` 加锁，持锁后重收集本排期 BOOKED 预约并过滤最新状态（`schedule/service.py:305`） |

未做：T6.5.9（前端交接文档，可选，F6.10/F6.11 实施时再产出）。

## 2. 文件级变更

| 文件 | 变更 |
|------|------|
| `apps/api/src/app/modules/booking/models.py` | 新增 `BookingReschedule`（约 52 行）；`CheckConstraint` 导入并格式化 import 块 |
| `apps/api/alembic/versions/f6a5b4c3d2e1_add_booking_reschedules.py` | 新增迁移（建表 + 索引 + 租户外键） |
| `apps/api/src/app/modules/booking/repository.py` | 2 个方法加 `exclude_booking_id`；`get_by_id_for_update` 加 `populate_existing`；新增 `BookingRescheduleRepository`（约 85 行） |
| `apps/api/src/app/modules/schedule/repository.py` | 新增 `get_by_ids_for_update`（约 34 行，含 `populate_existing`） |
| `apps/api/src/app/modules/schedule/service.py` | 新增 `get_schedules_for_update`（约 18 行）；T6.5.11 改写 `cancel_schedule` 锁序（约 +25 行）：先锁 booking(id ASC) 再锁 schedule，持锁后重收集并过滤 |
| `apps/api/src/app/modules/membership/service.py` | 新增 `lock_student_cards_for_booking_change`（约 24 行） |
| `apps/api/src/app/modules/booking/service.py` | 新增 `reschedule_booking` 及 8 个私有方法（约 530 行）；`_do_cancel_booking` 改为复用 `_assert_cancel_window` |
| `apps/api/src/app/modules/booking/schemas.py` | 新增 2 个 DTO |
| `apps/api/src/app/modules/booking/router.py` | 新增路由 + `Header` 导入 |
| `apps/api/tests/integration/test_booking_reschedule.py` | 新增，31 例 |
| `apps/api/tests/integration/test_booking_reschedule_concurrency.py` | 新增，9 例（含 D-6 双重回补/新约逃逸两条） |
| `apps/api/tests/membership_support.py` | 新增 `create_student`；`cleanup` 增加 `student_ids`；清理 `booking_reschedules` |
| `packages/api-types/openapi.json`、`schema.d.ts` | 生成物更新 |
| `docs/features/F6.0-membership-card-prototype/open-decisions.md` | D7 状态更新为「已实现（F6.5）」 |

## 3. 关键实现细节

- **锁顺序**：`pg_advisory_xact_lock(tenant, student)` → 旧 booking `FOR UPDATE` → 排期 `id ASC FOR UPDATE` → 学员卡集 `id ASC FOR NO KEY UPDATE` → 回补/扣次 → 单次 `commit()`。与 `create_booking`、`cancel_booking`、`finalize_schedule_bookings` 同序，不引入新的锁反转。
- **两种模式**：不同排期为「旧约 `CANCELLED` + 新约 `BOOKED`」，名额 -1/+1；同排期为原地更新 `membership_card_id`，名额不变、booking id 不变。
- **幂等**：优先 `Idempotency-Key`（≤64，部分唯一索引）；无键时按「旧约 `CANCELLED` + 审计记录参数比对」重放；同键不同参数返回 409。
- **审计占位**：改派无新 booking，`booking_reschedules.new_booking_id` 先落旧 booking id；改期在 `flush` 后回填新 booking id。
- **流水幂等键**：回补 `reschedule_{rid}_restore`；改期扣新卡 `booking_{new_id}_deduct`（沿用每笔次卡 booking 的键约定）；改派扣目标卡 `reschedule_{rid}_deduct`。
- **期卡 PENDING**：仅在目标卡为 PENDING 期卡时，按「取消旧约后的剩余预约 + 新约」重算锚点；不写 `valid_from/expire_at`。
- **失败回滚**：进入写入阶段（L475 起的 `try`）后，`HTTPException`、`BusinessException`、`IntegrityError`、未知异常均先 `rollback()` 再抛；写入前的状态/窗口/重复/卡校验异常不显式回滚（尚未产生写入，依赖会话生命周期兜底）。唯一约束/CHECK 映射为友好 400/409，不回显 SQL。

## 4. 与设计的偏差

| 项 | 设计 | 实现 | 原因 |
|----|------|------|------|
| 并发可见性 | 仅 `with_for_update()` | 额外 `.execution_options(populate_existing=True)` | 首轮并发测试暴露 identity map 旧快照，导致反向改期丢更新、跨学员超卖、改期 vs 取消双重回补（见 R1） |
| 迁移租户外键 | 草案未列 | 补 `tenant_id -> tenants.id ON DELETE CASCADE` + 索引 | 与 `TenantMixin` 一致，`alembic check` 无漂移 |
| 取消窗口 | 设计建议复用取消逻辑 | 抽 `_assert_cancel_window` 供取消/改期共用 | 避免复制规则；取消行为与文案不变 |
| 审计失败分支 | 设计未细化 | 改派/改期共用 `try` 块，失败整体回滚 | 保证审计行不悬空提交 |
| 幂等重放参数比对 | plan §7.4 要求比对 `old_membership_card_id` | 带 `Idempotency-Key` 时只比对目标参数，不比对旧卡 | 改派成功后 booking 卡已被改写，比对旧卡会把合法重试误判为 409（见 `service.py:644-647` 注释） |
| 响应模型 | 未指定 | `response_model=dict` | 与 booking 模块既有全部端点一致（模块统一信封约定） |

## 5. 验证结果

| 项 | 结果 | 证据 |
|----|------|------|
| 语法 | PASS | `py_compile` 8 个文件 |
| Lint | PASS | `ruff check` booking/schedule/membership service + 2 测试 + support → All checks passed |
| 功能 | PASS | `31 passed / 10.87s` |
| 并发 | PASS | `9 passed / 15.95s`（与功能合计 40）；D-6 两条连续 10 轮稳定 |
| 定向回归 | PASS | 93 passed（分两批：归属 10 单独执行；其余 83 含 RBAC 17） |
| 迁移 | PASS | `alembic downgrade -1` → `upgrade head` 往返成功；`alembic check` 无差异；head `f6a5b4c3d2e1` |

## 6. 风险与 UNKNOWN

| ID | 项 | 状态 |
|----|----|------|
| R1 | 并发旧快照缺陷 | 已修复并复测；`populate_existing` 已固化 |
| RK-1 | 排期取消与改期并发（D-6）可能重复回补 | **已修复（T6.5.11）**：取消排期按 booking(id ASC) → schedule 加锁并重收集；2 条并发用例连续 10 轮通过 |
| RK-2 | 期卡 PENDING 锚点漂移（U5） | 接受，审计表保留新旧排期 |
| RK-3 | 审计表不建业务 FK，可能产生孤儿引用 | 有意为之，避免阻断排期硬删除 |
| RK-4 | B-5/B-11 部分分支/B-14/B-15/C-9/D-7/D-9 | NOT VERIFIED，详见 `runtime-test-report.md` |
| RK-5 | 全量 pytest | 未执行（基线组按定向 + 回归集交付） |

## 7. Handoff

- 前端（F6.10/F6.11）：契约见 `implementation-plan.md` §8；写操作需二次确认；401 交既有 API 层刷新重放。
- 后续改动：不得绕过 `reschedule_booking` 直接改 booking/卡/排期；新增写路径必须沿用同一锁序。
- 排期取消链路硬化：T6.5.11 已完成（D-6），后续新增写路径必须沿用 booking(id ASC) → schedule 的同一锁序。
