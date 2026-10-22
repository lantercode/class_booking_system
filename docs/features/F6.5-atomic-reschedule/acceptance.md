# F6.5 验收标准：原子改期 / 原子改派

> 分组：A 静态 / B 运行时功能 / C 权限与租户 / D 并发与幂等 / E 回归。
> 判定原则：未执行或不可验证的一律记 `NOT VERIFIED` / `BLOCKED`，不得表述为 PASS。
> 测试环境：`pnpm db:up`（真实 PostgreSQL + Redis），集成测试使用真实 Uvicorn（端口 8765），禁止改回 in-process test client（`.trae/rules/testing/testing.md:16-20`）。

## A. 静态

| ID | 标准 | 判定方式 |
|----|------|----------|
| A-1 | 改动 Python 文件全部可编译 | `python3 -m py_compile` 逐文件 |
| A-2 | Ruff 通过 | `ruff check` 改动文件与新测试 |
| A-3 | 分层：Router 只做参数/依赖/调用/响应；业务判断在 Service | 代码审查 `booking/router.py` 新路由 |
| A-4 | Repository 继承 `TenantAwareRepository`；JOIN 查询显式叠加租户谓词 | 代码审查 `BookingRescheduleRepository`、`find_overlapping_active_booking` |
| A-5 | 禁止裸 SQL 业务查询；仅允许 advisory lock 原语 | 代码审查 |
| A-6 | 请求/响应 DTO 使用 Pydantic；`tenant_id/student_id` 不在请求体 | 代码审查 `booking/schemas.py` |
| A-7 | 新路由无尾斜杠（`redirect_slashes=False`），路径为 `/bookings/{booking_id}/reschedule` | 路由 diff |
| A-8 | OpenAPI 已包含新端点与请求体；`packages/api-types` 由 `pnpm gen:types` 生成，未手改 | `git diff packages/api-types` 仅生成产物 |
| A-9 | 迁移草案可 `upgrade/downgrade`；未在验收环境外执行 | `alembic upgrade head` + `alembic downgrade -1`（测试库） |
| A-10 | 无硬编码密钥；错误不回显 SQL/堆栈/内部主机 | 代码审查 + 错误响应抽样 |
| A-11 | 实际改动文件 ⊆ 白名单（见 implementation-plan §12） | `git status` / mtime 清单 |

## B. 运行时功能

> 前置：至少 2 个 `NORMAL` 且未开始的排期（同课程/不同课程各一）、1 张次卡、1 张期卡（ACTIVE/PENDING）、1 张无限卡、1 名学员。

| ID | 场景 | 预期 |
|----|------|------|
| B-1 | 次卡同卡改期（A→B） | 200；旧 booking `CANCELLED`、新 booking `BOOKED`；旧排期 `booked_count-1`、新排期 `+1`；旧卡 +1 后同卡 -1（净额不变）；存在 `RESTORE` 与 `CONSUME` 各 1 笔；`booking_reschedules` 1 条 |
| B-2 | 次卡异卡改期（旧卡 A→新卡 B） | 200；旧卡余额 +1；新卡余额 -1；新 booking `membership_card_id=B` |
| B-3 | 期卡 ACTIVE 同卡改期 | 200；不产生次数流水；卡 `valid_from/expire_at` 不变；新排期在有效期内 |
| B-4 | 期卡 PENDING 同卡改期到更晚排期 | 200；卡仍 PENDING；锚点按「取消旧约后的剩余预约 + 新约」重算；不写 `valid_from/expire_at` |
| B-5 | 期卡 PENDING 改派到另一张 PENDING 期卡 | 200；旧卡无激活；新卡仍 PENDING；两卡有效期未被改写 |
| B-6 | 纯改派（同排期换卡） | 200；`booking.id` 不变、`schedule_id` 不变、`status=BOOKED`、`membership_card_id` 变更；排期 `booked_count` 不变；无新 booking |
| B-7 | 同排期同卡（无变化） | 400「未发生改期或改派」；无写入 |
| B-8 | 目标排期已满 | 400「该排期已约满」；旧约 BOOKED；无卡变动 |
| B-9 | 目标排期与学员其他预约时间段重叠 | 400，文案含课程名与时间段（复用 F6.4）；旧约 BOOKED；无写入 |
| B-10 | 目标排期与旧约时间段重叠（排除自身后无其他冲突） | 200（只排除自身，不能误杀合法改期） |
| B-11 | 目标排期 `CANCELLED` / `FINISHED` / 已开始 / 超两周 / 未开放 / 已截止 | 400，分别返回对应文案 |
| B-12 | 旧约 `CHECKED_IN` / `COMPLETED` / `NO_SHOW` / `CANCELLED` | 400「当前预约状态无法改期」 |
| B-13 | 旧排期已过 `cancel_deadline` 或进入租户取消窗口 | 400；旧约不变（纯改派不受此限，见 B-6） |
| B-14 | 目标卡冻结/过期/非本人/跨租户/课程类型不适配 | 400 / 403 / 404；旧约与原卡不变 |
| B-15 | 目标次卡余额为 0（异卡） | 400「会员卡次数已用完」；旧约与原卡不变；目标名额未占 |
| B-16 | 原预约无卡 + 请求带新卡 | 400（D-5）；旧约不变 |
| B-17 | 原预约无卡 + 改期到另一排期且不带卡 | 200；新旧 booking 均无卡；名额正确迁移 |
| B-18 | 回补成功、扣次失败（注入异常/余额不足） | 整体回滚：旧约 BOOKED、旧卡余额不变、目标名额不变、无新 booking/审计行 |
| B-19 | 重复提交同一请求（同 `Idempotency-Key` 或同参数） | 200 重放同一新 booking；仅 1 条新 booking、1 条审计、1 次扣次 |
| B-20 | 同 `Idempotency-Key`、不同目标参数 | 409；不产生第二次变更 |

## C. 权限与租户

| ID | 场景 | 预期 |
|----|------|------|
| C-1 | 未登录调用 | 401 |
| C-2 | teacher 角色调用 | 403（`@require_roles("student")`） |
| C-3 | admin/super_admin 调用 | 403（本版不做代改） |
| C-4 | 学员 A 改学员 B 的预约 | 403，且不泄露 B 的预约详情 |
| C-5 | 跨租户用 A 的 token 改 B 租户 booking | 404（`TenantAwareRepository` 过滤） |
| C-6 | 使用其他学员的卡作为目标卡 | 403（`validate_card_for_booking`） |
| C-7 | 使用其他租户的卡 | 404 |
| C-8 | 请求体伪造 `student_id/tenant_id` | 字段不存在/被忽略；身份仍来自 `get_current_user` |
| C-9 | 审计表查询跨租户 | 只返回当前租户；Repository 继承 `TenantAwareRepository` |

## D. 并发与幂等

| ID | 场景 | 预期 |
|----|------|------|
| D-1 | 同一 booking 并发 2 个改期请求 | 恰好 1 次成功；另一方 200 重放或 409；仅 1 条新 booking、1 条审计；`booked_count` 准确 |
| D-2 | 同一学员并发 2 个改期到不同目标 | advisory lock 串行；两个都成功则目标各自 +1、旧约只取消一次；若第二个旧约已取消则 400/409 |
| D-3 | 同一学员并发「创建预约」与「改期」 | 不产生时间段重叠的两条进行中预约；advisory lock 生效 |
| D-4 | 反向改期（学员 A：S1→S2；学员 B：S2→S1） | 无死锁；按 schedule id ASC 加锁；结果可解释 |
| D-5 | 改期 vs 取消同一 booking | 一方成功，另一方按状态拒绝；无双重回补 |
| D-6 | 改期 vs 排期取消 | 同一预约回补恰好 1 次、无负余额；取消后的排期无残留 BOOKED；任一方向失败均不得产生孤儿预约 |
| D-7 | 改期 vs 签到/完成 | 行锁串行化；状态不会被覆盖 |
| D-8 | 事务失败注入（restore 后抛异常） | 全部回滚；无部分提交 |
| D-9 | 同旧 booking 的第二次改期（针对新 booking 再次改期） | 允许；`booking_reschedules` 新增一条，`old_booking_id=新 booking` |
| D-10 | 幂等键并发冲突（不同 booking 同 key） | 一方 409/唯一约束友好错误；不产生错误数据 |

> D-6 由 T6.5.11 排期取消锁硬化覆盖（2026-10-22 追加，用户要求先修复再关闭）：取消排期按 booking(id ASC) → schedule 加锁，并在持锁后重收集本排期 BOOKED 预约；用例见 `test_d6_reschedule_vs_schedule_cancel_no_double_restore`、`test_d6_reschedule_into_cancelled_schedule_no_orphan`。D-6 必须 PASS，不得再以 NOT VERIFIED 收口。

## E. 回归

| ID | 范围 | 命令/用例 |
|----|------|-----------|
| E-1 | 创建预约、取消、签到、完成 | `tests/integration/test_booking_card_authorization.py`、`test_booking_ownership.py`、`test_checkin_complete_lock.py` |
| E-2 | F6.3 卡状态机、扣次/回补、期卡激活 | `tests/integration/test_membership_card_deduct_lifecycle.py`、`test_membership_period_card_lifecycle.py`、`test_period_card_activation_concurrency.py` |
| E-3 | F6.4 时间段重叠 | `tests/integration/test_booking_time_overlap.py` |
| E-4 | 排期创建/取消/删除 | `tests/integration/test_schedule_create_concurrency.py`、`test_cancel_schedule_rollback.py`、`test_delete_schedule_service.py` |
| E-5 | 租户隔离与 RBAC | `tests/integration/test_tenant_isolation.py`、`test_rbac_enforcement.py` |
| E-6 | OpenAPI / 类型生成 | `pnpm gen:types` 后无 TS 报错；`packages/api-types` 仅生成变更 |

## 判定条件

- **功能达成**：B-1 ~ B-20 全部 PASS（其中 B-2/B-4/B-6/B-18/B-19 为必测核心）。
- **安全达成**：C-1 ~ C-9 全部 PASS。
- **并发达成**：D-1 ~ D-10 PASS（D-6 已由 T6.5.11 锁硬化并新增 2 条并发用例，必须 PASS）。
- **回归达成**：E-1 ~ E-6 全部 PASS；无法执行的记 `BLOCKED` / `NOT VERIFIED` 并说明。
- 任一 FAIL → `NEEDS_FIX`，回到开发阶段，不得进入人工验收。
