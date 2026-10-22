# F6.5 需求：原子改期 / 原子改派（D7）

> 来源：`docs/delivery/feature-backlog.md`「Feature 6.5」（L504-519）、`docs/features/F6.0-membership-card-prototype/open-decisions.md` D7（L55-60）与 D3/D6 相关条目。
> 设计阶段：2026-10-22。本文只做设计与代码对账，**不修改业务代码、不执行迁移、不运行测试**。
> 设计基线：当前工作区真实代码（含已落地的 F6.3、F6.4）。

## 1. 背景

当前改期只能由客户端执行「取消旧约 → 重新预约」两步：

1. `POST /api/v1/bookings/{id}/cancel` → `BookingService.cancel_booking`（`booking/service.py:238-255`）→ `_do_cancel_booking`（`booking/service.py:275-349`），在 `booking/service.py:345` 单独 `commit()`。
2. `POST /api/v1/bookings/` → `BookingService.create_booking`（`booking/service.py:61-236`），在 `booking/service.py:232` 单独 `commit()`。

两步之间真实存在「旧卡已回补、目标排期未锁定」的窗口：旧约已释放名额/回补课时，但目标排期可能已被他人抢满、目标卡已不可用、或第二步请求失败，导致学员两头落空。D7 已由产品负责人确认采用「新增原子改期端点」方案（`open-decisions.md:8,55-60,140`）。

F6.3/F6.4 已提供可复用的原子能力：

- `MembershipCardService.validate_card_for_booking`：卡状态/有效期/课程适用性校验（`membership/service.py:594-656`）。
- `MembershipCardService.deduct_credit`：卡集行锁 + 次卡扣次 + `booking_{booking_id}_deduct` 幂等键（`membership/service.py:1788-1870`）。
- `MembershipCardService.restore_credit`：次卡回补；期卡/无限卡 no-op（`membership/service.py:1872-1921`）。
- `MembershipCardService.activate_period_card_on_completion`：期卡首次完成激活（`membership/service.py:738-864`）。
- `BookingRepository.find_overlapping_active_booking`：跨排期时间段重叠校验（`booking/repository.py:176-216`）。
- `BookingRepository.lock_student_booking_scope`：`pg_advisory_xact_lock(tenant, student)`（`booking/repository.py:153-174`）。
- `BookingRepository.get_earliest_card_booking_start`：期卡预期有效期锚点（`booking/repository.py:368-396`）。

## 2. 目标

一次数据库事务内完成以下全部动作，任一步失败全部回滚：

```
回补原卡 → 锁定新排期（容量 + 时间段）→ 扣/校验新卡（可同卡）→ 旧约 CANCELLED + 新约 BOOKED
```

同时支持 D7 的「改派」：**同一排期下更换会员卡**，复用同一事务骨架、同一套行锁与幂等机制。

### 2.1 术语与两种模式

| 模式 | 触发条件 | 预约记录变化 | 名额变化 |
|------|----------|--------------|----------|
| 改期 `reschedule` | `new_schedule_id != old.schedule_id` | 旧约 `CANCELLED` + 新建 `BOOKED`（backlog 验收口径） | 旧排期 `-1`，新排期 `+1` |
| 改派 `card_swap` | `new_schedule_id == old.schedule_id` 且目标卡不同 | **原地更新**同一 booking 的 `membership_card_id`，状态仍 `BOOKED` | 不变 |

> 纯改派不新建 booking 的理由见 §7 D-1：同一排期「先取消再新建」会受部分唯一索引 `uq_bookings_schedule_student_active`（`booking/models.py:71-77`）约束，且会丢失原预约的 `booked_at` 与历史连续性。

## 3. 范围

### 3.1 In Scope（后端）

- 新增 `POST /api/v1/bookings/{booking_id}/reschedule`。
- 新增 `BookingRescheduleRequest` / `BookingRescheduleResponse` DTO。
- `BookingService` 新增原子复合事务方法，覆盖改期与改派两种模式。
- `BookingRepository`：
  - `find_active_booking` / `find_overlapping_active_booking` 支持排除「正在改期的这条预约」。
  - 新增 `BookingRescheduleRepository`（审计 + 幂等记录）。
- `ScheduleRepository` / `ScheduleService`：按 id ASC 批量锁定两个排期。
- `MembershipCardService`：新增「按 id ASC 锁定学员卡集」的入口，供复合事务在回补/扣次前统一加锁。
- 新增审计表 `booking_reschedules`（迁移草案见 `implementation-plan.md` §6）。
- 新增集成测试：功能、回滚、并发、幂等、权限、租户、回归。
- 更新 OpenAPI 并执行 `pnpm gen:types`（生成产物不得手改）。

### 3.2 Out of Scope（明确不做）

- 不做 UI；由 F6.10 / F6.11 消费契约。
- 不做批量改期 / 批量改派。
- 不恢复「自动取消旧约后重约」的旧语义；不提供「无确认自动改期」。
- 不做管理员/教师代改（本版只允许学员本人；见 D-6）。
- 不做 MCP Tool / AI 意图（`/ai/chat` 本版不能改期；见 §9）。
- 不做改期通知推送（F6.2）。
- 不做退款、差价、支付（F6.1）。
- 不改 F6.3 卡状态机、不改 F6.4 重叠判定口径、不改排期创建冲突逻辑。

## 4. 用户故事

| # | 角色 | 故事 |
|---|------|------|
| US-1 | 学员 | 我想把已约课程换到另一个还有名额的同课程排期，系统一次完成，不出现「旧课已退、新课没抢到」。 |
| US-2 | 学员 | 我的原卡被冻结/临期，我想把同一节课换到另一张可用卡，不想先取消再重约。 |
| US-3 | 学员 | 我重复点击「确认改期」或网络重试时，不希望生成两条新预约或重复扣次。 |
| US-4 | 机构 | 改期失败时，原预约、原卡额度、目标名额必须保持原样，不能产生脏数据。 |

## 5. 业务规则（设计口径）

| # | 规则 |
|---|------|
| R-1 | 只有 `BookingStatus.BOOKED` 的预约允许改期/改派；`CHECKED_IN/COMPLETED/NO_SHOW/CANCELLED` 一律拒绝（`booking/models.py:12-17`）。 |
| R-2 | 改期时旧排期不得已开始；改派（同排期换卡）同样要求排期未开始。 |
| R-3 | 改期遵循旧排期的取消窗口：`cancel_deadline` 与租户 `booking_cancel_minutes`（复用 `booking/service.py:301-318` 语义）；纯改派不释放名额，不受取消窗口限制。 |
| R-4 | 目标排期必须 `NORMAL`、未开始、未超过「未来两周」、在 `booking_opens_at` / `booking_closes_at` 窗口内、`booked_count < capacity`（对齐 `create_booking` 的 `booking/service.py:73-95`）。 |
| R-5 | 目标排期不得与该学员其他进行中预约时间段重叠；判定复用 F6.4 半开区间，并**排除正在改期的这条预约**。 |
| R-6 | 目标排期不得已有该学员的其他有效预约（`find_active_booking` 口径，`booking/repository.py:123-151`），唯一索引作兜底。 |
| R-7 | 目标卡必须属于该学员、同租户、状态可预约、按目标排期日校验有效期、课程类型/课程适用（复用 `validate_card_for_booking`，`membership/service.py:594-656`）。 |
| R-8 | 次卡：回补原卡 + 扣减目标卡；**同卡也执行「回补再扣」**（净额不变），以保证每笔 booking 都有对应 `CONSUME` 流水，避免后续取消时超额回补。 |
| R-9 | 期卡/无限卡：`restore_credit` 为 no-op（`membership/service.py:1894-1898`）；不修改目标卡 `valid_from/expire_at`。期卡 PENDING 的预期有效期锚点按「取消旧约后的剩余预约 + 新预约」重算。 |
| R-10 | 原预约无会员卡时，本版不允许通过改派附加会员卡（D-5）。 |
| R-11 | 任一步失败整体回滚：旧约保持 `BOOKED`、原卡额度不变、目标名额不占、无审计/幂等记录。 |
| R-12 | 写操作必须幂等：同一旧预约的并发/重试请求至多产生一次改期；重复请求返回既有结果或明确冲突。 |
| R-13 | 身份与租户只来自已认证上下文；请求体不接收 `student_id/tenant_id`。 |
| R-14 | 审计记录必须落库：旧/新 booking、旧/新 schedule、旧/新 card、操作人、模式、请求键。 |

## 6. 真实代码对账（spec vs code）

> 行号均来自本次实际读取的当前工作区代码。

| # | 事实 | 证据 |
|---|------|------|
| C1 | 当前路由有 create / list / get / cancel(by id) / cancel(by schedule) / check-in / complete，**无 reschedule** | `booking/router.py:22-42,45-116,119-133,136-157,160-181,189-203,206-220` |
| C2 | `create_booking` 校验顺序：排期存在/状态/容量/时间窗口 → 同排期查重 → 卡快路径校验 → F6.4 重叠 → 占名额 → 插 booking → 扣次 → 一次 commit | `booking/service.py:73-95,97-99,101-121,123-140,142-144,159-164,184-230,232-233` |
| C3 | 取消是独立事务，commit 在 `_do_cancel_booking` 内 | `booking/service.py:275-349`，commit 在 `:345` |
| C4 | 取消窗口：`cancel_deadline` + 租户 `booking_cancel_minutes`（默认 90） | `booking/service.py:301-318` |
| C5 | 取消仅拒绝 `CANCELLED`、`CHECKED_IN`、`COMPLETED`；未显式拒绝 `NO_SHOW` | `booking/service.py:295-299` |
| C6 | 旧约归属校验使用 `booking.student_id != student_id` → 403 | `booking/service.py:248-255` |
| C7 | `find_active_booking` 状态含 `BOOKED/CHECKED_IN/COMPLETED`，不支持排除指定 booking | `booking/repository.py:123-151` |
| C8 | `find_overlapping_active_booking` 只查 `BOOKED/CHECKED_IN`，**无 `exclude_booking_id`**，会命中自身 | `booking/repository.py:176-216` |
| C9 | 学员维度 advisory lock 已存在，事务级自动释放；双键 `(int4,int4)` | `booking/repository.py:153-174` |
| C10 | booking 行 `FOR UPDATE` 读取已存在，供取消/签到/完成使用 | `booking/repository.py:267-289` |
| C11 | 排期 `booked_count` 增减分别用 `FOR UPDATE SKIP LOCKED` / `FOR UPDATE` | `schedule/repository.py:182-208,210-225` |
| C12 | 排期单行 `FOR UPDATE` 已有 Service 入口 | `schedule/service.py:529-550` |
| C13 | 排期时间字段带时区；容量 CHECK 约束 `booked_count <= capacity AND >= 0` | `schedule/models.py:42-48,71-74` |
| C14 | 卡集锁 `FOR NO KEY UPDATE` + `populate_existing`，按 id ASC；默认只锁 ACTIVE/PENDING/FROZEN | `membership/repository.py:229-273` |
| C15 | 卡单行锁同样 `FOR NO KEY UPDATE` + `populate_existing` | `membership/service.py:501-531` |
| C16 | `deduct_credit` 幂等键检查在加锁前；次卡才增减 `used_credits`，期卡/无限卡 `total_credits is None` 不扣次 | `membership/service.py:1806-1810,1812-1815,1832-1848,1857-1869` |
| C17 | `restore_credit` 幂等键检查在加锁前；非次卡直接 no-op；次卡 `used_credits <= 0` 抛 400 | `membership/service.py:1886-1898,1899-1921` |
| C18 | 交易表 `idempotency_key` 有部分唯一索引 | `membership/models.py:299-317` |
| C19 | 期卡 PENDING 预约校验会锁学员卡集，并按传入锚点计算预期窗口 | `membership/service.py:659-736`；锚点查询 `booking/repository.py:368-396` |
| C20 | 新 booking 插入使用 `auto_commit=False` + `flush()`，保证与扣次同事务 | `booking/service.py:159-164`；`base_repository.py:164-197` |
| C21 | 部分唯一索引 `uq_bookings_schedule_student_active` 覆盖 `status IN (1,3,4)` | `booking/models.py:71-77` |
| C22 | 错误码体系：`BusinessException` 默认 500，可显式 400；`PermissionException` 403；`NotFoundException` 404 | `core/exceptions.py:13-30` |
| C23 | `require_roles("student")` 用于学员写端点，装饰器从 `db/current_user/redis_client` 获取上下文 | `booking/router.py:29,142,166`；`core/rbac/decorator.py:155-259` |
| C24 | 响应统一走 `success(data=..., msg=...)` 信封；路由 `response_model=dict` | `booking/router.py:22-42` |
| C25 | 交易表幂等键查询自动叠加当前租户 | `membership/repository.py:447-464` |
| C26 | `BookingResponse` 已含 `membership_card_id`、`display_status`、课程/时间/教师字段 | `booking/schemas.py:29-59`；`booking/service.py:782-840` |

## 7. Conflict（文档/预期 vs 真实代码）

| Conflict | Evidence | Impact | Recommendation |
|----------|----------|--------|----------------|
| backlog 称两个独立 commit 在 `booking/service.py:156,269` | 真实 commit 在 create `:232`、cancel `:345`；`:156` 是 `if data.membership_card_id`，`:269` 是 `find_by_schedule_and_student` | 行号已漂移，不影响结论「两步非原子」 | 文档统一改用真实行号；实现不受影响 |
| backlog 称路由仅 create/list/get/cancel/check-in/complete | 真实还存在 `POST /bookings/cancel`（按 schedule 取消） | 端点清单少一项 | 以 `booking/router.py:160-181` 为准 |
| backlog 验收写「旧约 CANCELLED + 新约 BOOKED」 | 该口径适用于**改期**；纯改派若照搬会与 `uq_bookings_schedule_student_active`（`booking/models.py:71-77`）冲突，并丢失原 booking 历史 | 改派语义不清晰，可能产生重复记录 | 区分两种模式：改期 = cancel+new；同排期换卡 = 原地更新（D-1） |
| `transaction.md` 规定锁顺序 booking → schedule → card | `create_booking` 真实顺序是 advisory → schedule 行锁 → 插入 booking → card（`booking/service.py:125-144,159-230`）；插入的 booking 尚无既有行可锁 | 若机械套用会误判 create 违规 | 规则解释为「对**既有** booking 行先锁」；改期按 advisory → booking → schedule(id ASC) → card(id ASC)。create 的插入不构成锁序反转 |
| F6.4 重叠查询不支持排除自身 | `booking/repository.py:176-216` 无 `exclude_booking_id` | 改期到与旧约重叠的排期会被自身误判冲突（例如改到同一天相邻时段） | 新增可选 `exclude_booking_id`，仅改期路径传入旧 booking id |
| 现有扣次幂等键是 `booking_{booking_id}_deduct` | `booking/service.py:186`；`membership/service.py:1807-1810` | 同排期改派若复用该键，幂等检查会命中旧流水并跳过扣次 | 改派使用独立键 `reschedule_{reschedule_id}_deduct`；改期新 booking 仍用 `booking_{new_booking_id}_deduct` |
| `restore_credit` 对非次卡 no-op，对次卡要求 `used_credits > 0` | `membership/service.py:1897-1900` | 原卡为过期次卡但 `used_credits=0` 时改期会 400 | 作为 fail-closed 语义保留；由取消/改期统一返回「原卡次数异常，无法改期」 |
| 排期硬删除会删除该排期全部 booking | `schedule/service.py:406-438`；`booking/repository.py:250-265` | 若审计表对 `old_booking_id/new_booking_id` 建 FK RESTRICT，删除排期会被阻断 | 审计表使用裸 BIGINT 快照，不建 booking FK（D-10） |
| 排期取消流程未对 booking 行加锁 | `schedule/service.py:341-379` 用 `search` 后直接改状态/回补 | 与改期并发时可能重复回补（旧债 D-F6.4-2 的延伸） | 列为 D-5 并发验收项；若复现，单开硬化任务补 `FOR UPDATE` + 状态重检，不在 F6.5 顺手扩大范围 |

## 8. UNKNOWN（待确认 / 待实测）

| # | 项 | 当前事实 | 处理 / 推荐 |
|---|----|----------|-------------|
| U1 | 改期是否应受旧排期取消窗口限制 | 取消窗口真实存在（`booking/service.py:301-318`） | 推荐：改期受限；纯改派不受限（D-3） |
| U2 | 管理员/教师是否可代改 | 当前 create/cancel 均 `@require_roles("student")`（`booking/router.py:29,142`） | 推荐：本版仅学员本人；代改另立需求（D-6） |
| U3 | 无卡预约能否通过改派附加卡 | 当前 `create_booking` 允许无卡（`booking/service.py:156-157`） | 推荐：本版拒绝，避免意外扣次（D-5） |
| U4 | 同排期同卡请求的响应 | 无现成语义 | 推荐：无幂等键时 400「未发生改期或改派」；有匹配幂等记录时重放（D-3/D-11） |
| U5 | 期卡 PENDING 在旧约取消后的锚点漂移 | 锚点取最早非取消预约（`booking/repository.py:368-396`） | 推荐：接受漂移，按取消后剩余预约重算；在审计中记录新旧排期供解释 |
| U6 | 过期次卡仍有剩余次数时回补是否成功 | `restore_credit` 不检查卡状态，仅检查类型与 `used_credits`（`membership/service.py:1893-1900`） | 推荐：沿用现状，可回补到过期卡；产品需确认过期卡余额是否可继续使用（D-4） |
| U7 | 排期取消 vs 改期并发是否重复回补 | 排期取消未锁 booking（`schedule/service.py:341-379`） | 必须实测；若复现，登记技术债并在后续硬化 |
| U8 | `Idempotency-Key` 保留期与清理 | 无 HTTP 幂等表 | 推荐：审计表随业务保留，不做自动清理；key 仅 64 字符（D-2） |
| U9 | 改期后统计口径 | 旧约变 CANCELLED 会进入取消统计 | 推荐：报表按 `booking_reschedules` / `cancelled_reason` 前缀区分「改期取消」；需产品确认（D-1） |
| U10 | 多实例部署下 advisory lock | `pg_advisory_xact_lock` 是数据库级，跨实例有效 | 可用；ID 超 2^31 溢出为既有债 D-F6.4-1 |
| U11 | 前端确认交互与 F6.10/F6.11 排期 | 本版不做 UI | 契约冻结后由 frontend-engineer 消费；需产品确认改期入口位置 |
| U12 | 时区展示 | 冲突文案固定 `Asia/Shanghai`（`booking/service.py:47-49,720-734`） | 沿用现状，多区域部署另立需求 |

## 9. 依赖与风险

### 9.1 Dependencies

| 依赖 | 状态 | 说明 |
|------|------|------|
| F6.3 卡状态机 / 期卡语义 | 已合并 | `validate_card_for_booking`、`deduct_credit`、`restore_credit`、期卡 no-op |
| F6.4 时间段重叠校验 | 已合并 | 复用查询与文案；需扩展 `exclude_booking_id` |
| `packages/api-types` 生成链路 | 可用 | `pnpm gen:types`（根 `package.json`） |
| Alembic | 可用 | 新增审计表迁移 |
| 前端 F6.10/F6.11 | 未开始 | 本版只冻结契约，不实现 UI |

### 9.2 Risks

| # | 风险 | 等级 | 缓解 |
|---|------|------|------|
| RK-1 | 锁顺序错误导致死锁 | 高 | 固定 advisory → booking → schedule(id ASC) → card(id ASC)；并发反向改期用例实测 |
| RK-2 | 同卡「回补再扣」被误简化成 no-op，导致后续取消超额回补 | 高 | 明确 R-8；用例断言两笔流水与净额 |
| RK-3 | 改派复用 `booking_{id}_deduct` 导致扣次被幂等跳过 | 高 | 改派使用 `reschedule_{rid}_deduct`（§implementation-plan 幂等表） |
| RK-4 | 目标排期在锁前/锁后状态变化 | 中 | 锁后重检 `status/capacity/时间窗口` |
| RK-5 | 排期取消未锁 booking，重复回补 | 中 | D-5 并发用例；必要时单开硬化任务 |
| RK-6 | 审计表 FK 阻断排期硬删除 | 中 | 审计表不建 booking FK |
| RK-7 | 期卡 PENDING 锚点漂移引发预期窗口变化 | 中 | 重算锚点；产品确认（U5） |
| RK-8 | 取消统计被改期污染 | 低 | `booking_reschedules` 区分；报表口径确认（U9） |

## 10. 验收口径摘要

详见 `acceptance.md`。核心必须 PASS：

- 改期成功：旧约 `CANCELLED` + 新约 `BOOKED` 同事务；旧排期 `-1`、新排期 `+1`；次卡净额不变 / 换卡正确增减。
- 任一步失败：旧约仍 `BOOKED`、卡额度不变、目标名额不占。
- 纯改派：同一 booking、同一排期，卡变更，状态仍 `BOOKED`，名额不变。
- 目标满员 / 时间段重叠 / 卡不可用 / 越权 / 跨租户均拒绝且无副作用。
- 重复提交：至多一次改期，重复请求返回既有结果或明确冲突。

## 11. 待产品负责人拍板的决策（D-1 ~ D-11）

> 每条给出推荐选项与理由；未拍板前不进入编码。

| # | 决策 | 推荐选项 | 理由 |
|---|------|----------|------|
| D-1 | 改期用「更新原 booking.schedule_id」还是「旧约 CANCELLED + 新约 BOOKED」 | **改期 = 旧约 CANCELLED + 新约 BOOKED；同排期纯改派 = 原地更新 booking.membership_card_id** | 与 backlog 验收口径一致；保留旧约历史与审计；纯改派若 cancel+new 会撞部分唯一索引并丢失 `booked_at` 连续性 |
| D-2 | 幂等机制：HTTP `Idempotency-Key` / 服务端确定性键 / booking 字段 | **状态 + 审计表为主，`Idempotency-Key` 为可选增强**：`booking_reschedules` 记录 old/new booking、request_key；同旧 booking 的改期至多一条 | 不引入通用 HTTP 幂等表；复用现有「字符串幂等键 + 唯一索引」风格；重试可重放 |
| D-3 | 允许改期的状态与时间窗口 | **仅 `BOOKED` 且旧排期未开始；改期受 `cancel_deadline` / 租户 `booking_cancel_minutes` 限制；纯改派不受取消窗口限制** | 改期实际释放名额，需与取消口径一致；改派不释放名额，不应被取消窗口阻断（尤其 F6.7 卡失效救援） |
| D-4 | 换卡时旧卡回补；同卡是否「回补再扣」；期卡改派 | **次卡一律回补原卡；同卡也回补再扣；期卡/无限卡 no-op；期卡可换到另一张可预约的 PENDING/ACTIVE 期卡，且不修改任何一张卡的有效期** | 同卡 no-op 会让新 booking 缺少 CONSUME 流水，后续取消会超额回补；F6.3 已定期卡 no-op；有效期属于卡的产品规则，改期不应改写 |
| D-5 | 原预约无卡时能否通过改派附加卡 | **本版拒绝（400）** | 避免「免费约的课被改派后突然扣次」；如产品需要，另立规则与确认交互 |
| D-6 | 权限与归属 | **仅学员本人**；`@require_roles("student")` + Service 归属校验；管理员/教师代改不做 | 与现有 create/cancel 权限一致；代改涉及 RBAC 新权限与审计，另立需求 |
| D-7 | 错误码语义 | **404 资源不存在（含跨租户）；403 非本人/非本人卡；400 状态/窗口/容量/同排期同卡；409 期卡区间冲突或幂等键冲突** | 与现有 `NotFoundException/PermissionException/BusinessException` 及 F6.3 的 409 保持一致 |
| D-8 | 容量事务与行锁顺序 | **advisory(tenant,student) → 旧 booking FOR UPDATE → 两个 schedule 按 id ASC FOR UPDATE → 学员卡集按 id ASC FOR NO KEY UPDATE → 回补/扣次**；改期不使用 `SKIP LOCKED` | 符合 `database/transaction.md` 的既有行先锁原则；id ASC 消除反向改期死锁；与 create 的 schedule→card 顺序一致 |
| D-9 | 目标排期重叠校验如何排除自身 | **给 `find_overlapping_active_booking` / `find_active_booking` 增加可选 `exclude_booking_id`，改期路径传入旧 booking id** | 现有查询会命中自身；只排除自身，不放过其他真实冲突 |
| D-10 | 是否需要 DB 迁移 | **需要：新增 `booking_reschedules` 审计/幂等表；不建 booking FK（裸 BIGINT 快照）** | 排期硬删除会删 booking（`schedule/service.py:406-438`），FK 会阻断删除；审计表还承载幂等与统计口径 |
| D-11 | 响应契约 | **`data = { mode, previous_booking_id, previous_status, booking }`；`booking` 复用 `BookingResponse`** | 前端一次拿到「旧约 id + 新约完整信息」，无需二次查询；新增字段属于兼容变更 |
