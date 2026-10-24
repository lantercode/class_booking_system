# F4.4 — Review

> 日期：2026-10-02 ｜ 审查人：database-engineer（自审 + 规则清单）

## Scope

- 变更严格限于 Feature 定义：
  1. 新建 migration `f44ab1c2d3e4_add_status_check_constraints.py`（越界 fail-fast 校验 + `create_check_constraint` x3；downgrade `drop_constraint` x3）。
  2. `booking/models.py` `__table_args__` 补 `CheckConstraint("status IN (1, 2, 3, 4, 5)", name="ck_bookings_status")`；import 补 `CheckConstraint`。
  3. `schedule/models.py` `__table_args__` 补 `CheckConstraint("status IN (1, 2, 3)", name="ck_course_schedules_status")`。
  4. `membership/models.py` `__table_args__` 补 `CheckConstraint("status IN (0, 1, 2, 3, 6)", name="ck_membership_cards_status")`。
  5. 新增测试 `test_status_check_constraints.py`（18 用例）。
- Service / Repository / Router / schemas / OpenAPI / 前端 / MCP 均未改动。
- 未引入新依赖、未改 OpenAPI 路径/方法/请求体/响应模型、未改 Redis。

## Architecture

- 分层合规：Check 约束在 DB 层（migration），对 Service/Repository 透明；Service/Repository 零改动。
- migration 走 Alembic `op.create_check_constraint` / `op.drop_constraint`，非手写 SQL 脚本；越界校验用 `op.execute(sa.text(...))` 是结构变更前置校验（非业务读写）。
- 事务边界：越界校验 + ADD CONSTRAINT 在同一 migration upgrade（alembic `Will assume transactional DDL`），原子完成。
- 租户隔离：Check 约束不涉及租户过滤；`TenantAwareRepository` 语义不变。
- 与 F4.1/F4.2 同范式（同一事务内先处理存量再建约束），但策略差异：status 非法值无语义安全的自动修正目标，故采用 fail-fast（非防御性清理），在 `UNKNOWN U1` 与 `D2` 中透明记录。

## Code

- migration：`revision=f44ab1c2d3e4` / `down_revision=f42cd3e4f5a6`；约束名显式 `ck_bookings_status` / `ck_course_schedules_status` / `ck_membership_cards_status`（便于 downgrade 精确 drop）。
- 模型：三张表 `__table_args__` 约束名、合法值集合与 migration 完全一致；`CheckConstraint` import 仅在 booking 需新增（schedule/membership 已有 `CheckConstraint` import）。
- downgrade：反序 drop 三个 Check 约束（与 upgrade 反序，安全可审计）；不恢复数据（Check 约束不修改存量数据）。

## Security

- 无端点变更；`@require_permissions` / `get_current_user` 未动。
- 租户隔离：Check 约束不影响 `tenant_id` 过滤。
- DB 层 Check 为最后兜底：非法 status 写入触发 `IntegrityError`，经全局异常处理器返回统一信封，不回显 SQL/traceback。
- migration 内 SQL 不含敏感信息；约束名稳定可审计。

## Transaction / Concurrency

- **核心修复**：在 DB 层为三表 status 增加取值范围兜底。
  - 修复前：status 无 DB 层约束，非法值可绕过应用层写入。
  - 修复后：任何写入路径（ORM / 裸 SQL）的非法 status 均被 Check 约束拦截。
- 越界校验 + 建约束原子事务：alembic `Will assume transactional DDL` → 校验 + ALTER 在一个事务内，若校验失败则整体回滚。
- `ON UPDATE` / `ON DELETE`：Check 约束不关联外键，无级联行为。
- 并发风险：Check 约束本身不引入锁；migration upgrade 期间仅 ALTER TABLE ADD CONSTRAINT（PG 对 CHECK 不锁全表，仅对目标表取 `ACCESS SHARE` → `SHARE UPDATE EXCLUSIVE`），对读写影响极小。生产灰度若担心瞬间 `SHARE UPDATE EXCLUSIVE` 阻塞并发 DDL，可任选低峰期执行。

## Migration

- revision 链：`down_revision=f42cd3e4f5a6`（F4.2 后唯一 head）；应用后 `alembic heads` 仍单 head `f44ab1c2d3e4`，无分叉。
- 可逆性（AC-13 手动验证）：`alembic downgrade -1` → 三约束消失、alembic_version=f42cd3e4f5a6；`alembic upgrade head` → 三约束恢复、alembic_version=f44ab1c2d3e4。往返成功。
- 数据变更：无（Check 约束不修改存量数据）；dev 库 0 越界通过校验；生产若有越界 fail-fast 回滚。
- downgrade 不恢复数据（Check 约束不修改数据）。

## Regression

- `test_booking_fk_membership_card.py`（F4.1，6/6）：**通过**。
- `test_order_fk_membership_card.py`（F4.2，7/7）：**通过**。
- 本 Feature 不动 bookings/orders 的 FK / 索引，仅新增 status Check → F4.1/F4.2 行为不受影响。
- Service/Repository 零改动 → 业务逻辑零回归风险。

## Acceptance

- AC-1/2/3（约束存在）：`test_check_constraint_exists[ck_*_status]` x3 通过。
- AC-4/5/6（非法值拒绝）：`test_*_invalid_status_rejected` x9 通过。
- AC-7/8/9（合法值放行）：`test_*_valid_statuses_succeed` x3 通过。
- AC-10（存量数据未破坏）：`test_no_out_of_range_status_and_data_present` x3 通过。
- AC-11（回归）：F4.1 6/6 + F4.2 7/7 通过。
- AC-12（分层合规）：静态 grep 验证 Service/Repository 零改动、模型与 migration 一致（详见 [static-verification.md](./static-verification.md)）。
- AC-13（可逆）：`alembic downgrade -1` + `alembic upgrade head` 往返成功。

## 遗留事项（不阻塞）

1. 生产灰度时若存在越界 status 行，upgrade 会 fail-fast 抛错回滚并打印明细（表/status/行数），需人工核查修正后重跑。
2. `membership_cards` 既有 Check 命名漂移（模型 `chk_credits_range` vs DB `chk_used_credits_valid`/`chk_total_credits_positive`）为存量历史差异，未来 autogenerate 对齐时可另立 Feature。
3. 其他带 status 的表（users/courses/classrooms/orders 等）当前未加 Check 约束；如有需求需另立 Feature 评估。

## 结论

**READY_FOR_ACCEPTANCE**
