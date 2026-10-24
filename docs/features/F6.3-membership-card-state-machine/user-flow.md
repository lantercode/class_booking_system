# F6.3 — 会员卡扣次与期卡激活状态机：User Flow

- 状态：DESIGN
- 分组：基线组（按现状完整流程执行，不启用效率优化）
- 适用范围：后端 Service / Scheduler / HTTP 契约；不包含前端页面改造。
- 行号基于 2026-10-22 当前工作区。
- 测试声明：本文所有流程均未执行验证；对应验收项在 `acceptance.md` 标记 `PLAN_NOT_RUN`。

## 0. 术语与判定函数

### 0.1 状态枚举（真实代码）

| 对象 | 枚举 | 证据 |
|------|------|------|
| 会员卡 | PENDING=0 / ACTIVE=1 / EXPIRED=2 / FROZEN=3 / CANCELLED=6 | `apps/api/src/app/modules/membership/models.py:49-56` |
| 预约 | BOOKED=1 / CANCELLED=2 / CHECKED_IN=3 / COMPLETED=4 / NO_SHOW=5 | `apps/api/src/app/modules/booking/models.py:12-17` |
| 排期 | NORMAL=1 / CANCELLED=2 / FINISHED=3（无 COMPLETED） | `apps/api/src/app/modules/schedule/models.py:12-15` |
| 卡类型 | count / period / unlimited | `apps/api/src/app/modules/membership/models.py:42-46` |

### 0.2 统一判定函数（设计契约）

```text
is_bookable_card(card, student_id, tenant_id, schedule, course) =
    card.tenant_id == tenant_id
    AND card.student_id == student_id
    AND (
        card.status == ACTIVE
        OR (card.status == PENDING AND card.card_type == period AND card.valid_from IS NULL)
    )
    AND card_matches_course(card, course)
    AND schedule_date_within_card_validity(card, schedule)
```

- `schedule_date_within_card_validity`：以 `schedule.start_at` 的日期为基准（不是 `now`）。
  - `card.valid_from` 非空时：`schedule.start_at.date() >= card.valid_from.date()`。
  - `card.expire_at` 非空时：`schedule.start_at.date() <= card.expire_at.date()`（D4：`expire_at` 当天 23:59:59 前可用）。
  - `card.valid_from IS NULL` 且 `card.expire_at IS NULL` 且 `card_type=period` 且 `status=PENDING`：视为“有效期待定”，允许预约（D9）。
- `card_matches_course`：
  - `applicable_course_type_code` 非空时必须等于 `course.course_type_code`（字段见 `apps/api/src/app/modules/course/models.py:138`）。
  - `applicable_course_ids` 非空时，`schedule.course_id` 必须在其列表中。
- `expected_interval(card, schedule, anchor_start_at)`（仅期卡预约预校验用）：
  - 对 `PENDING + valid_from IS NULL` 的期卡，`anchor = 该卡已存在的非取消预约中最早的 schedule.start_at；无则为当前 schedule.start_at`；
  - `start = anchor` 的日期 00:00:00。
  - `end = start.date() + (validity_days - 1)` 的 23:59:59；与 `_calc_expire_at` 一致（`membership/service.py:1468-1488`）。
  - 新排期的日期必须落在 `[start.date(), end.date()]` 内，否则拒绝（同一张期卡的多次预约必须落在同一个有效期窗口内）。
  - `validity_days` 取卡片快照（本次新增列）；缺失时回退 `product.validity_days`，仍缺失则拒绝预约。
- 区间重叠（闭区间，复用现有口径）：
  - `a.start <= b.end AND b.start <= a.end`（`membership/service.py:708-710`，`membership/service.py:314-319`）。

### 0.3 期卡状态机

```text
发卡 ──> PENDING (valid_from=NULL, expire_at=NULL)
           │
           ├─ 预约（不扣次、不激活、写 booking.membership_card_id）
           │
           ├─ 首次 COMPLETED / NO_SHOW ──> ACTIVE
           │        valid_from = 排期日 00:00:00
           │        expire_at  = 排期日 + validity_days - 1 23:59:59
           │        ISSUE 流水（change=0，幂等键 booking_{id}_period_activate）
           │
           ├─ 预约取消 / 排期取消 ──> 仍 PENDING（不激活、不回补）
           ├─ freeze ──> 拒绝（400）
           └─ 发卡满 90 天且无 COMPLETED/NO_SHOW ──> CANCELLED

ACTIVE ──> expire_at < now ──> EXPIRED（次卡剩余次数清零；期卡次数为 NULL）
```

### 0.4 次卡状态机

```text
预约 ──> used_credits + 1（CONSUME，幂等键 booking_{id}_deduct，同一事务）
取消 ──> used_credits - 1（RESTORE，幂等键 booking_{id}_restore）
完成/缺席 ──> 无卡操作（“确认”= no-op）
过期 ──> EXPIRED，剩余次数清零（EXPIRE 流水）
```

---

## 1. 次卡流程

### F-A 次卡预约预扣（现状保留 + 新增前置校验）

| 项 | 内容 |
|----|------|
| 触发 | `POST /api/v1/bookings`（`apps/api/src/app/modules/booking/router.py:22-41`），请求体含 `membership_card_id`（`booking/schemas.py:12-17`） |
| 前置条件 | 排期为 NORMAL（`booking/service.py:66-67`）；未约满（`:69-70`）；未开始（`:74-75`）；两周窗口（`:77-79`）；预约开放/截止（`:81-84`）；无重复预约（`:86-88`）；卡属于当前学员、当前租户、类型为 count、状态 ACTIVE、排期日在有效期内、课程适用 |
| 主要步骤 | 1) 校验排期与重复预约；2) 校验卡（新增统一校验）；3) `increment_booked_count`（`booking/service.py:90-92`，`schedule/repository.py:181-207`）；4) `repo.create(auto_commit=False)` 插入 BOOKED（`booking/service.py:108-110`）；5) `deduct_credit`（`booking/service.py:129-154`），对卡 `FOR UPDATE`（`membership/service.py:1348`）；6) 统一 `commit`（`booking/service.py:155`） |
| 事务边界 | 名额递增、booking INSERT、卡扣次、CONSUME 流水共享同一 `AsyncSession`；任一失败整体回滚（`database/transaction.md:10-13`） |
| 失败分支 | 卡不存在/跨租户 → 404；卡不属于学员 → 403；非 ACTIVE/无余额/排期日超出有效期/课程不适用 → 400；任何卡异常使 `db.rollback()` 后以业务错误返回（`booking/service.py:140-153`） |
| 幂等语义 | 同一学员同一排期由部分唯一索引兜底（`booking/models.py:71-77`）；扣次幂等键 `booking_{booking.id}_deduct`（`booking/service.py:131`）；重复提交在 INSERT 阶段被约束拒绝，不会产生第二次扣次 |
| 锁顺序 | `schedule`（容量递增）→ `booking`（INSERT 新行）→ `membership_cards`（扣次）。与 `database/transaction.md:22-25` 的“booking → schedule → card”存在差异，理由：创建路径尚无 booking 行可锁；该差异为既有实现，F6.3 不改变顺序，见 `implementation-plan.md` 的冲突 C-14 |

### F-B 次卡取消回补

| 项 | 内容 |
|----|------|
| 触发 | `POST /api/v1/bookings/{id}/cancel` 或 `POST /api/v1/bookings/cancel-by-schedule`（`booking/router.py:136-186`） |
| 前置条件 | 操作者为预约所属学员（`booking/service.py:171-176`）；booking 存在且未 CANCELLED/CHECKED_IN/COMPLETED（`:219-223`）；未超过取消截止时间（`:225-242`） |
| 主要步骤 | 1) booking `FOR UPDATE`（`:214`）；2) 状态重检；3) 置 CANCELLED；4) `decrement_booked_count`（`:250`）；5) 若 `membership_card_id` 且卡为 count → `restore_credit`（`:252-267`）；6) `commit`（`:269`） |
| 事务边界 | booking 状态、名额递减、卡回补、RESTORE 流水同一事务 |
| 失败分支 | 已取消/已签到/已完成 → 400；超时 → 400；回补异常 → 500，整单回滚（`booking/service.py:263-267`） |
| 幂等语义 | booking 行锁 + 状态重检；回补幂等键 `booking_{booking.id}_restore`（`:254`）；重复取消第二次拿到锁后 400 |
| F6.3 变化 | 取消前先读卡类型：count → 回补；period/unlimited → no-op，不写流水，不因 `used_credits=0` 抛 400（修复 `membership/service.py:1427-1434` 的期卡缺陷） |

### F-C 次卡完成/缺席确认（无操作）

| 项 | 内容 |
|----|------|
| 触发 A | 手动完成 `POST /api/v1/bookings/{id}/complete`（`booking/router.py:206-213`，`booking:manage`） |
| 触发 B | 排期自动结束 `auto_finish_expired_schedules`（`schedule/scheduler.py:44-122`）→ 收口到 `BookingService.finalize_schedule_bookings` |
| 前置条件 | 手动：booking 为 BOOKED 或 CHECKED_IN（`booking/service.py:323-324`）；自动：排期 NORMAL 且 `end_at + grace < now`（`schedule/scheduler.py:73-79`） |
| 主要步骤 | 手动：booking `FOR UPDATE` → 状态重检 → 置 COMPLETED → 若期为 period 则激活 → commit。自动：逐排期锁 booking → 锁 schedule → 重检 → 置 FINISHED → CHECKED_IN→COMPLETED、BOOKED→NO_SHOW → 若期为 period 则激活 → commit |
| 卡操作 | 次卡：完全不触碰卡（不扣、不回补、不写流水）。期卡：仅首次激活。无限卡：不触碰 |
| 事务边界 | booking 终态与期卡激活同一事务；激活失败整体回滚 |
| 失败分支 | 重复/非法状态手动完成 → 400 “当前预约状态无法完成”（保持既有语义，`test_checkin_complete_lock.py:10` 的 AC-6 依赖）；激活失败 → 回滚，booking 保持原状态 |
| 幂等语义 | booking 行锁 + 状态重检；自动任务重复运行因排期已 FINISHED 而 no-op；次卡无额外写操作，天然幂等 |

---

## 2. 期卡流程

### F-D 期卡发卡：PENDING + 有效期留空

| 项 | 内容 |
|----|------|
| 触发 | `POST /api/v1/membership/cards`（`membership/router.py:178-205`，`admin`/`super_admin`） |
| 前置条件 | 产品存在（若传）；`card_type=period` 必须有 `validity_days`（现有校验 `membership/service.py:385-391`）；调用者租户来自 `current_user.tenant_id`（`membership/router.py:198`） |
| 主要步骤 | 1) Service 幂等检查（若传 key，`membership/service.py:244-248`）；2) 读取产品；3) 计算 `validity_days = data.validity_days or product.validity_days`（`:258`）；4) **period 分支跳过**发卡期冲突检查（`:265-353`）与续卡最早生效计算（`:355-383`）；5) 设置 `status=PENDING`、`valid_from=None`、`expire_at=None`；6) 写入 `validity_days` 快照；7) 插入卡与 ISSUE 流水（`change_amount=0`，`:456-468`）；8) Router commit（`membership/router.py:203`） |
| 事务边界 | 卡与 ISSUE 流水同一事务；Router 统一 commit |
| 失败分支 | 产品不存在 → 404；period 缺 `validity_days` → 400；角色不足 → 403（装饰器） |
| 幂等语义 | Service 支持 `idempotency_key`，但当前 Router 未传（P18）；重复点击可能生成多张卡，记录为风险，不在本 Feature 扩接口 |
| 历史兼容 | 旧逻辑已产生的“带 `valid_from/expire_at` 的 PENDING 期卡”继续由 `auto_activate_membership_cards` 处理（`membership/scheduler.py:136-141`），本流程只约束新发卡 |

### F-E 期卡预约：不扣次 + 预期有效期冲突预校验

| 项 | 内容 |
|----|------|
| 触发 | `POST /api/v1/bookings`，`membership_card_id` 指向 period 卡 |
| 前置条件 | F-A 的全部排期前置；`is_bookable_card()` 为真；卡快照或产品可提供 `validity_days` |
| 主要步骤 | 1) 排期/重复预约校验；2) 读取课程并校验课程适用性；3) 无锁快路径校验卡归属/租户/类型/状态/排期日有效期；4) 若卡为 ACTIVE 期卡：只做 D4 排期日校验，不再做预期窗口/冲突检查，跳至第 5 步；5) 查询该卡已存在的非取消预约，取最早 `schedule.start_at` 作为预期窗口锚点；6) `increment_booked_count`；7) 插入 booking（`auto_commit=False`），写入 `membership_card_id`；8) 对同学员、同租户的非终态卡按 `id ASC` 加 `FOR UPDATE`（状态 ACTIVE/PENDING/FROZEN），复检卡；9) 以锚点计算 `expected_interval`，并校验新排期日落在窗口内；10) 与同学员、同课程类型、非自身的非终态卡做闭区间重叠，命中 → 409；11) **不调用 `deduct_credit`**；12) commit（任一步失败整体回滚，名额与 booking 一并撤销） |
| 事务边界 | 卡集锁、名额、booking INSERT 同一事务；冲突或校验失败整体回滚，名额递增与 booking 一并撤销 |
| 失败分支 | 卡跨租户 → 404；卡不属于学员 → 403；卡非 ACTIVE/非 D9-PENDING → 400；排期日早于 `valid_from` 或晚于 `expire_at` → 400；课程不适用 → 400；新排期日超出该卡预期窗口 → 400；预期区间冲突 → 409；缺 `validity_days` → 400（配置错误，提示联系管理员） |
| 幂等语义 | 同一排期重复预约由 `find_active_booking`（`booking/repository.py:123-151`）+ 部分唯一索引（`booking/models.py:71-77`）拦截；期卡预约不写卡流水，重复请求不会产生扣次副作用 |
| 并发语义 | 学员卡集锁使同一学员的并发期卡预约串行；两张 `valid_from=NULL` 的 PENDING 卡之间无法计算预期区间，可能同时通过，属 UNKNOWN-1/R2，由激活阶段的冲突检查兜底 |
| 空状态 | 不传 `membership_card_id` → 按无卡预约路径（现状允许）；`applicable_course_ids` 为空视为不限课程，`applicable_course_type_code` 为空视为不限类型 |

### F-F 期卡首次激活：手动完成路径

| 项 | 内容 |
|----|------|
| 触发 | `POST /api/v1/bookings/{id}/complete`（`booking:manage`） |
| 前置条件 | booking 为 BOOKED/CHECKED_IN（`booking/service.py:323-324`）；booking 带 `membership_card_id`；卡为 period |
| 主要步骤 | 1) booking `FOR UPDATE`（`:318`）；2) 状态重检；3) 读取排期（用于排期日；只读不加锁，`start_at` 不可变）；4) 锁同学员非终态卡集（`id ASC`，含自身）；5) 重检卡状态：ACTIVE/EXPIRED/CANCELLED/FROZEN → no-op（ACTIVE 为非首次）；PENDING → 冲突检查；6) 计算 `valid_from/expire_at`；7) `status=ACTIVE`，写 ISSUE 流水（幂等键 `booking_{booking.id}_period_activate`，`change_amount=0`）；8) booking 置 COMPLETED；9) 统一 commit |
| 事务边界 | 激活与 booking 完成同一事务；任一步失败 → 不 commit → 全部回滚 |
| 失败分支 | 缺 `validity_days` → 400；激活区间与已有卡冲突 → 409/400（基线 fail-closed，整单回滚，booking 保持原状态）；卡状态非法 → no-op 或 400（见下） |
| 幂等语义 | booking 行锁 + 状态重检保证只执行一次；卡 `ACTIVE` 重检保证重复调用 no-op；ISSUE 流水 `idempotency_key` 唯一（`membership/models.py:294-311`） |
| 重复完成 | 第二次请求拿到锁后状态已 COMPLETED → 400 “当前预约状态无法完成”，与既有测试一致，不改为 no-op |

### F-G 期卡首次激活：排期自动结束路径（Scheduler → Service）

| 项 | 内容 |
|----|------|
| 触发 | `auto_finish_expired_schedules` 每 5 分钟运行（`main.py:77-88`）；候选为 `end_at < now - grace` 且 NORMAL（`schedule/scheduler.py:73-79`）；开关 `AUTO_FINISH_ENABLED`（`config.py:61-62`） |
| 前置条件 | 逐租户设置 ContextVar（`schedule/scheduler.py:65-67`）；排期仍 NORMAL |
| 主要步骤 | 1) Scheduler 查询候选排期（只读）；2) 对每个排期调用 `BookingService.finalize_schedule_bookings(db, schedule_id)`；3) Service 查询 booking id 列表（只读）；4) 按 `id ASC` 锁 booking；5) 锁 schedule 并重检 NORMAL（已 FINISHED/CANCELLED → no-op）；6) 置 FINISHED；7) 逐 booking 重检：CHECKED_IN→COMPLETED、BOOKED→NO_SHOW；8) 对带 period 卡的 booking 执行 F-F 的激活步骤；9) 单排期 commit；10) Scheduler 记录成功/失败并继续下一个排期 |
| 事务边界 | 单排期一个事务；booking 终态、schedule 状态、期卡激活同事务；失败整排期回滚，下一轮重试 |
| 失败分支 | 单排期异常 → 记录 tenant/schedule/booking/card，rollback，继续其他排期；不中断其他租户（沿用 `schedule/scheduler.py:116-120` 的隔离策略） |
| 幂等语义 | 排期 FINISHED 后不再进入候选；booking 状态重检；卡 ACTIVE 重检 + ISSUE 幂等键；任务重复执行 no-op |
| 排除 | 不引入 `ScheduleStatus.COMPLETED`；不处理 CANCELLED 排期；不处理 CHECKED_IN 之外的历史异常状态 |

### F-H 期卡取消：不激活、不回补

| 项 | 内容 |
|----|------|
| 触发 A | 学员取消预约（`booking/router.py:136-158`） |
| 触发 B | 排期取消（`schedule/router.py:169-186` → `schedule/service.py:304-403`） |
| 前置条件 | 预约为 BOOKED；未超过取消截止（`booking/service.py:225-242`）；排期非 CANCELLED/FINISHED（`schedule/service.py:327-331`） |
| 主要步骤 | booking `FOR UPDATE` → 状态重检 → 置 CANCELLED → 名额递减 → 若卡为 count 回补；period/unlimited → no-op → commit |
| 卡状态 | 期卡保持 PENDING，`valid_from/expire_at` 仍为 NULL；不写 RESTORE 流水 |
| 失败分支 | 已签到/已完成无法取消（400）；排期取消回补阶段任何异常整体回滚（`schedule/service.py:370-378`） |
| 幂等语义 | booking 行锁 + 状态重检；期卡无写操作 |

### F-I 期卡/次卡过期扫描（ACTIVE + PENDING）

| 项 | 内容 |
|----|------|
| 触发 A | `auto_expire_membership_cards` 每 5 分钟（`main.py:94-101`） |
| 触发 B | `auto_activate_membership_cards` 执行前的 `_expire_cards_in_transaction`（`membership/scheduler.py:51-103,132-134`） |
| 前置条件 | `expire_at IS NOT NULL AND expire_at < now`；状态 ACTIVE 或 PENDING |
| 主要步骤 | 逐租户设置 ContextVar → 查询候选 → 逐卡 `FOR UPDATE` → 状态重检 → 次卡剩余次数清零并写 EXPIRE；期卡写 EXPIRE（change=0）→ `status=EXPIRED` → commit |
| 事务边界 | 单租户一个事务；单卡失败记录并继续（沿用现有策略） |
| 失败分支 | 单卡异常 → 记录，继续；租户异常 → 回滚该租户，继续下一租户 |
| 幂等语义 | 状态重检；EXPIRED 不再被查询命中；重复执行 no-op |
| 说明 | D9 新期卡 `expire_at=NULL` 不会被命中；旧 PENDING 带 `expire_at` 的卡会被正确清理 |

### F-J PENDING 期卡 90 天未激活作废

| 项 | 内容 |
|----|------|
| 触发 | 新增 `auto_cancel_pending_membership_cards`，默认每天一次（可配置） |
| 前置条件 | `card_type=period`、`status=PENDING`、`created_at < now - PENDING_CARD_CANCEL_DAYS`（默认 90）；且不存在该卡关联的 COMPLETED/NO_SHOW booking（R-B7 “无任何完成记录”） |
| 主要步骤 | 逐租户设置 ContextVar → 查询候选 → 逐卡 `FOR UPDATE` → 状态重检 → 置 CANCELLED、`cancelled_at=now`、`cancelled_reason="超期未激活（90天）"` → 写 EXPIRE（change=0，remark 可审计）→ commit |
| 事务边界 | 单租户一个事务；单卡失败隔离 |
| 失败分支 | 单卡异常记录继续；租户异常回滚该租户 |
| 幂等语义 | 状态重检；CANCELLED 不再命中；重复执行 no-op |
| 配置 | 新增 `PENDING_CARD_CANCEL_DAYS: int = 90`（`core/config.py`）；不得硬编码在 Scheduler |

### F-K PENDING 不可冻结

| 项 | 内容 |
|----|------|
| 触发 | 管理端冻结会员卡（`membership/service.py:608-672`） |
| 前置条件 | 卡存在且属于当前租户 |
| 主要步骤 | `get_card_with_lock` → 状态检查：FROZEN/EXPIRED/CANCELLED 保持原 400；新增 PENDING → 400 “未激活卡不可冻结” → 不改 `expire_at/frozen_*`，不写冻结记录 |
| 事务边界 | 只读校验；失败不 commit |
| 幂等语义 | 重复冻结 FROZEN → 400，保持现状 |
| 历史兼容 | 旧 PENDING 带 `valid_from` 同样拒绝冻结 |

---

## 3. 横切状态与异常语义

### 3.1 空 / Loading / Error / Success

| 状态 | 后端契约 | 说明 |
|------|----------|------|
| 空 | 卡不存在 → 404；学员无卡 → 预约允许不传卡；期卡无 `validity_days` → 400（不是空列表） | `/membership/my-cards` 的空列表行为不变（`membership/router.py:245-255`） |
| Loading | 后端无进度通道，HTTP 一次性响应；F6.3 不引入 SSE/流式 | 前端按钮 loading 属 F6.10/F6.11 |
| Error | 统一信封 `{code,msg,data}`；业务错误使用 400/403/404/409，系统错误 500；不返回 traceback/SQL/内部主机名 | 既有异常体系；不得在卡激活失败时只返回 200 |
| Success | `code=0`；预约响应含 `status` 与 `membership_card_id`（`booking/schemas.py:29-59`） | 期卡预约成功时 `membership_card_id` 必须回填，便于后续激活 |

### 3.2 403 / 租户隔离

| 场景 | 期望 |
|------|------|
| 角色不足（非 admin 发卡、非 student 预约、无 booking:manage 完成） | 403，由 RBAC 装饰器在进入 Service 前拦截（`core/rbac/decorator.py:99-152,205-259`） |
| 跨租户访问卡 | 404 或 403，且错误信息不暴露卡是否存在；查询必须带 `tenant_id`（`membership/service.py:491-498`） |
| 使用他人卡 | 403 “无权使用此会员卡”；不得因卡状态校验通过而放行 |
| 定时任务 | 逐租户 `set_tenant_id(tenant_id)`（`membership/scheduler.py:125-127`、`schedule/scheduler.py:65-67`）；任务结束 `set_tenant_id(None)` |
| 前端传入 tenant_id | 一律忽略；租户只取自已认证上下文与 ContextVar（`security/tenant-isolation.md`） |

### 3.3 并发与幂等矩阵

| 竞争场景 | 保护机制 | 结果 |
|----------|----------|------|
| 并发创建同一学员同一排期预约 | `find_active_booking` + 部分唯一索引（`booking/models.py:71-77`） | 一成一败；失败方回滚名额 |
| 并发扣次同一张次卡 | 卡 `FOR UPDATE`（`membership/service.py:1348`）+ `used_credits` 检查 | 串行扣次，不超扣 |
| 并发取消同一预约 | booking `FOR UPDATE` + 状态重检（`booking/service.py:214-223`） | 一次成功，第二次 400 |
| 并发完成同一预约 | booking `FOR UPDATE` + 状态重检（`booking/service.py:318-324`） | 一次成功，第二次 400（既有 AC-6） |
| 并发手动完成 + 定时 finalize | 两者都锁 booking；状态重检 | 只有一方推进状态，另一方 no-op/400 |
| 并发激活同一期卡 | 卡集 `FOR UPDATE` + ACTIVE 重检 + ISSUE 幂等键 | 只激活一次、只写一条流水 |
| 并发发卡（count） | 发卡前锁学员非终态卡集（`membership/service.py:265-278`） | 冲突检查不被绕过 |
| 并发期卡预约（不同卡、相近排期） | 卡集锁只能串行，无法比较两个 NULL 区间 | 可能都通过；激活阶段冲突检查兜底（R2/UNKNOWN-1） |
| 定时任务重复运行 | 排期 FINISHED / booking 终态 / 卡 ACTIVE / 卡 CANCELLED 状态重检 | no-op |
| 取消与排期自动结束并发 | 取消锁 booking；finalize 锁 booking 后锁 schedule 并重检 NORMAL | 先取消的排期不会被 finalize；先 FINISHED 的排期不能取消（`schedule/service.py:330-331`） |

### 3.4 错误信息与审计

- 卡激活失败必须记录：`tenant_id`、`schedule_id`、`booking_id`、`card_id`、`card_status`、`expected_valid_from/expire_at`、错误原因；不得记录 token、SQL、堆栈到响应。
- 流水审计：ISSUE（激活）、CONSUME（次卡预扣）、RESTORE（次卡回补）、EXPIRE（过期/作废）均带 `card_id`、`booking_id`（可空）、`idempotency_key`（可空）、`operator_id`（系统任务为空）。
