# F6.3 — 会员卡扣次与期卡激活状态机：Requirement

- 状态：DESIGN（设计冻结前的对账产物）
- 分组：基线组（按现状完整流程执行，不启用任何效率优化）
- 来源：`docs/delivery/feature-backlog.md:430-464`（Feature 6.3）
- 对账时间：2026-10-22；本文所有行号基于当前工作区代码，代码变更后必须重新对账。
- 约束：本阶段仅新增文档；未修改 `apps/**`、`.trae/**`、`.github/**`、`docs/delivery/feature-backlog.md`、`docs/features/F6.0-*`；未安装依赖；未执行 git checkout/reset/stash。
- 测试声明：本文不声称任何测试已执行。所有未运行的验证在 `acceptance.md` 中标记为 `PLAN_NOT_RUN`。

## Goal

把已冻结的产品规则 D1 / D4 / D5 / D9 落到后端 Service 与 Scheduler，形成两条可验证的生命周期闭环：

1. 次卡：预约预扣 → 取消回补 → 课程完成/缺席不重复扣次（“确认”为无操作幂等语义）。
2. 期卡：发卡 PENDING 且有效期留空 → 预约不扣次并做预期有效期区间冲突预校验 → 首次课程完成/缺席激活并写入真实有效期 → 过期扫描与 90 天未激活作废。

同时消除当前“Scheduler 直接批量改写业务状态”的分层违规，把排期结束的预约终态处理收口到 `BookingService`。

## Problem（现状与真实代码证据）

| ID | 问题 | 真实代码证据 | 对 Goal 的影响 |
|----|------|--------------|----------------|
| P1 | 期卡发卡即计算 `valid_from=now`、`expire_at`，并可能直接置为 ACTIVE | `apps/api/src/app/modules/membership/service.py:397-429`（`valid_from = data.valid_from or now`，`valid_from <= now` 则 ACTIVE，随后 `_calc_expire_at`）；`membership/service.py:436-452` 写入卡 | 与 D9“发卡即 PENDING、`valid_from/expire_at` 留空”直接冲突，期卡在首次完成前就拥有有效期 |
| P2 | 期卡发卡阶段仍执行同课程类型有效期重叠检查，且以 `now` 作为新卡起点 | `membership/service.py:265-353`（锁学员 PENDING/ACTIVE/FROZEN 卡，`temp_valid_from = data.valid_from or now`，用 `validity_days` 计算临时区间） | 期卡有效期本应在首次完成时确定；发卡期检查既无可靠区间，又会误拒绝合法发卡 |
| P3 | `deduct_credit` 要求 `status=ACTIVE`，并用 `now` 校验有效期 | `membership/service.py:1348-1363`（非 ACTIVE 抛 400；`now < valid_from`、`now > expire_at` 抛 400） | D9 期卡为 PENDING，无法走现有扣次；且以“当前时间”而非“排期日”校验，违反 D4 的排期日口径 |
| P4 | 期卡/无限卡在 `deduct_credit` 中不扣次，但仍写一条 `change_amount=-1` 的 CONSUME 流水 | `membership/service.py:1365-1368`（`total_credits is None` 时 `balance_after=0`）；`membership/service.py:1390-1401`（固定 `change_amount=-1`） | 期卡若复用扣次会产生错误流水；必须按期卡分支为“完全不调用扣次” |
| P5 | `restore_credit` 无卡类型分支，`used_credits <= 0` 直接 400 | `membership/service.py:1405-1449`（`used_credits <= 0` 抛 400；期卡也会 `used_credits -= 1`） | 期卡预约不扣次，取消时若调用回补会 400，导致整个取消预约/取消排期事务回滚 |
| P6 | 课程完成只改 booking 状态，不触碰会员卡 | `apps/api/src/app/modules/booking/service.py:305-332`（加 booking 行锁、状态重检、`status=COMPLETED`、commit；无卡调用） | D1 的“COMPLETED 确认”无实现；D9 的“首次完成激活”无实现 |
| P7 | 排期结束由 Scheduler 直接 bulk update 预约状态，不触发卡激活 | `apps/api/src/app/modules/schedule/scheduler.py:90-111`（排期置 FINISHED；`update(Booking)` CHECKED_IN→COMPLETED、BOOKED→NO_SHOW；直接 commit） | 自动结束路径完全绕过 Service，既不激活期卡，也违反 `architecture/layering.md` 的 Scheduler 收口要求 |
| P8 | `ScheduleStatus` 只有 NORMAL/CANCELLED/FINISHED，不存在 COMPLETED | `apps/api/src/app/modules/schedule/models.py:12-15` | 设计不得引入不存在的 `ScheduleStatus.COMPLETED`；完成触发点必须是 booking 的 COMPLETED/NO_SHOW |
| P9 | `freeze_card` 未拒绝 PENDING | `membership/service.py:624-632`（只拦 FROZEN/EXPIRED/CANCELLED） | 违反 R-B7 b)“未激活卡不可冻结”；冻结还会改写 `expire_at`（`membership/service.py:655-660`） |
| P10 | 过期扫描仅 ACTIVE | `apps/api/src/app/modules/membership/scheduler.py:283-289`（`status == ACTIVE`） | R-B7 c) 要求扫描 `ACTIVE, PENDING`；带 `expire_at` 的 PENDING 卡不会被清理 |
| P11 | 自动激活任务会把带 `valid_from` 的 PENDING 卡直接激活，并用产品天数补算有效期 | `membership/scheduler.py:136-141`（`valid_from <= now AND status=PENDING`）；`:203`（直接 ACTIVE）；`:206-227`（按产品 `validity_days` 计算） | D9 新期卡 `valid_from=NULL` 不会被该查询命中，但“PENDING 只允许首次完成激活”的规则没有显式隔离，需在设计上固定枚举与空值语义 |
| P12 | 无 90 天 PENDING 期卡自动作废任务，也无对应配置 | `apps/api/src/app/main.py:77-142`（仅注册 auto_finish / auto_expire / auto_activate / notify / auto_unfreeze / auto_cancel_underbooked 六个任务）；`apps/api/src/app/core/config.py:61-66`（无 90 天配置项） | R-B7 a) 无实现 |
| P13 | 预约链路没有期卡预期有效期区间校验 | `apps/api/src/app/modules/booking/service.py:51-159`（仅排期状态/容量/时间窗口/重复预约/名额递增/插 booking/按 card_id 调 deduct） | D9 的“预约时按排期日 + validity_days 计算预期有效期并做区间重叠判断”无实现 |
| P14 | 预约链路没有卡归属、课程适用性、排期日有效期的统一校验 | `booking/service.py:51-159` 未校验 `card.student_id == student_id`、未校验 `applicable_course_type_code/applicable_course_ids`；`membership/service.py:1348-1368` 仅校验卡状态与当前时间 | 学员可传同租户他人卡或不适用的卡；前端过滤（`apps/miniapp/src/pages/student/booking-confirm/index.vue:336-352`）不构成后端授权 |
| P15 | `get_active_cards_by_student` 只返回 ACTIVE | `apps/api/src/app/modules/membership/repository.py:201-227`（`status.in_([ACTIVE])`，并排除过期） | R-B7 要求与“已有同课程类型 ACTIVE/PENDING 卡”做区间重叠；PENDING/FROZEN 卡不在查询结果中，冲突检查必然漏判 |
| P16 | 会员卡没有 `validity_days` 快照字段 | `apps/api/src/app/modules/membership/models.py:146-239`（仅有 `valid_from`/`expire_at`/`total_credits`/`used_credits`/`status` 等） | 期卡发卡时可以选择显式 `data.validity_days`（`membership/schemas.py:114-131`），但字段未落库；首次完成激活时无法可靠还原发卡时的天数 |
| P17 | 取消排期只处理 BOOKED 预约 | `apps/api/src/app/modules/schedule/service.py:340-347`（`status=BOOKED` 才进入循环） | D1 说“排期 CANCELLED 时回补”；已 CHECKED_IN 的预约不会被回补（当前无对应产品路径，记录为边界风险） |
| P18 | 发卡 HTTP 入口未传 `idempotency_key` | `apps/api/src/app/modules/membership/router.py:198-205`（Service 支持 `idempotency_key`，Router 未传）；Service 幂等检查见 `membership/service.py:244-248` | 管理员重复点击可能生成多张 PENDING 期卡；本 Feature 不新增 API 参数，记录为风险 |
| P19 | 小程序把所有 PENDING 卡置为不可用 | `apps/miniapp/src/pages/student/booking-confirm/index.vue:277-286` | F6.3 不改前端；后端能力先行的阶段，端到端 UI 选择期卡仍不可用，运行时验收需走 API/直接构造数据 |

## User Story

- US-1（学员，次卡）：我在预约时使用次卡，系统预扣 1 次；我取消预约时次数回补；课程完成或我缺席时不再额外扣次。
- US-2（学员，期卡）：我拿到一张期卡时它处于“待激活”且没有有效期；我用它预约某节未来课程时系统不扣次，但会检查“以该排期日推算的有效期”是否与我已有同课程类型卡重叠；课程完成后卡首次激活，有效期从该排期日起算。
- US-3（管理员）：我可以发放期卡，但期卡不会在发卡时获得有效期；PENDING 期卡不能被冻结；90 天内没有任何完成记录的 PENDING 期卡会自动作废。
- US-4（系统/教师）：排期结束后，系统按规则把已签到预约标记完成、未到课预约标记缺席，并在同一事务内完成期卡首次激活；期卡激活失败不得留下“booking 已完成但卡未激活”的半状态。
- US-5（安全/运维）：任何卡操作都必须限定在当前租户与当前学员；并发完成、并发取消、重复定时任务不得重复扣次或重复激活。

## Scope

### In Scope（逐项）

1. **S1 期卡发卡状态机**：`card_type=period` 时强制 `status=PENDING`、`valid_from=NULL`、`expire_at=NULL`；把发卡时确定的 `validity_days` 持久化为卡片快照；期卡发卡不再执行基于“当前时间 + 天数”的同课程类型冲突拒绝。见 T6.3.1。
2. **S2 期卡预约校验**：新增 Service 层校验与预期有效期计算；期卡预约不调用 `deduct_credit`；预期有效期以“该卡最早非取消预约的排期日”为锚点（无则为当前排期日），新排期必须落在锚点窗口内，并与同学员、同租户、同课程类型的非终态卡做闭区间重叠判断。见 T6.3.2。
3. **S3 卡归属与适用性前置校验**：预约时校验卡属于当前学员、属于当前租户、卡类型允许本次预约、排期课程在卡的适用范围内、排期日落在卡有效期内。见 T6.3.2。
4. **S4 次卡完成/缺席确认**：课程完成/缺席不额外扣次、不回补；重复完成请求保持现有 400 语义（不改成 no-op），靠 booking 行锁 + 状态重检保证只处理一次。见 T6.3.3。
5. **S5 期卡首次完成激活**：手动完成与排期自动结束两条路径都调用同一个 Service 方法；激活写入 `valid_from=排期日 00:00:00`、`expire_at=排期日 + validity_days - 1 的 23:59:59`，并写幂等 ISSUE 流水。见 T6.3.3 / T6.3.4。
6. **S6 排期终态收口**：`schedule/scheduler.py` 不再直接 `update(Booking)` 或直接改 `ScheduleStatus`；改为逐排期调用 `BookingService.finalize_schedule_bookings`。见 T6.3.4。
7. **S7 取消回补分支**：次卡取消/排期取消回补；期卡与无限卡取消为 no-op，不写 RESTORE 流水，不因 `used_credits=0` 抛 400。见 T6.3.5。
8. **S8 冻结与过期**：`freeze_card` 拒绝 PENDING；两处过期处理（任务内预处理与 auto_expire 任务）扩展为 `status IN (ACTIVE, PENDING) AND expire_at IS NOT NULL`。见 T6.3.6。
9. **S9 90 天未激活作废**：新增可配置任务，把发卡超过 N 天（默认 90）仍为 PENDING 的期卡置为 CANCELLED，并写审计流水。见 T6.3.6。
10. **S10 数据与索引评估**：为 `validity_days` 快照新增可空列及回填迁移；复核现有索引是否覆盖新增扫描，无必要不新增索引。见 `implementation-plan.md` 的迁移章节。
11. **S11 测试**：新增期卡生命周期、预约校验、完成激活并发、过期/90 天任务测试，并回归 F2.3/F2.4/F4.1/F4.4/F4.5。见 T6.3.7。

### Out of Scope（逐项）

1. **D2 用尽状态**：不新增 EXHAUSTED 状态；次卡用尽后仍为 ACTIVE，仅由 `deduct_credit` 的余额检查拒绝。
2. **D3 失效替代与受影响预约**：不做换卡、替代卡推荐、受影响预约提示。
3. **D6 多卡推荐与排序**：不改前端选卡排序（当前小程序排序见 `booking-confirm/index.vue:551-614`）。
4. **D7 改期/改派**：不新增改期、改派端点；不改变“取消 + 重约”的既有路径。
5. **D8 退款**：不涉及退款、订单、支付。
6. **D10 跨排期时间段重叠校验**：属 F6.4，不在本 Feature 内；期卡有效期区间校验与排期时间段校验必须解耦。
7. **前端页面改造**：不改 admin/student/teacher Web、小程序任何页面；小程序 PENDING 不可用问题（P19）保持现状，由后续 UI Feature 处理。
8. **通知推送**：不改 `notify_expiring_membership_cards` 的提醒逻辑（F6.2）。
9. **AI Tool 扩展**：不改 `ai/mcp_server.py` 的 `create_booking` 入参；AI 预约当前不传 `membership_card_id`（`apps/api/src/app/ai/mcp_server.py:260-290`），因此不涉及期卡；若未来支持，必须复用同一 Service 校验。
10. **发卡接口幂等参数**：不新增 `Idempotency-Key` 请求头或 schema 字段；P18 仅记录为风险。
11. **取消排期对 CHECKED_IN 的补偿**：不扩大 `cancel_schedule` 的预约状态范围；P17 记录为边界风险。
12. **性能优化**：不引入缓存、批量并行、批量 upsert、异步任务拆分；沿用现有逐租户、逐卡处理的基线实现。
13. **数据库结构以外的契约变更**：不改任何既有 HTTP 路径、请求/响应 DTO 字段；不新增公开端点。

## 引用 F6.0 已冻结规则

| 规则 | 冻结结论 | 本 Feature 的落点 | 证据 |
|------|----------|-------------------|------|
| D1 | 预约预扣 + 排期 COMPLETED 确认；期卡预约不扣次，首次 COMPLETED 激活；签到/完成只推进 booking 状态，不再触碰卡（对次卡而言“确认”是无操作） | 次卡继续在 `create_booking` 预扣、取消回补；`complete_booking`/finalize 只对期卡执行激活，对次卡不改卡 | `docs/features/F6.0-membership-card-prototype/open-decisions.md:13-18`；`business-rules.md:28-31` |
| D4 | `expire_at` 当天 23:59:59 前可预约可签到；未来生效的 PENDING 卡不可预约 | 预约校验以“排期日”而不是 `now` 判断有效期；D9 期卡（`valid_from IS NULL`）例外可预约 | `open-decisions.md:34-38`；`business-rules.md:55` |
| D5 | 缺席自动消解：排期 COMPLETED 即扣/激活，NO_SHOW 保留但不再决定扣不扣 | NO_SHOW 与 COMPLETED 一样触发期卡首次激活；次卡不额外扣 | `open-decisions.md:41-46`；`business-rules.md:56` |
| D9 | 发卡即 PENDING、有效期留空；预约不激活不扣次；按排期日 + `validity_days` 算预期有效期并与同学员同课程类型 ACTIVE/PENDING 卡做区间重叠；首次 COMPLETED 激活；排期 CANCELLED 不激活；PENDING 90 天未完成作废；freeze 拒绝 PENDING；EXPIRED 扫描扩展至 ACTIVE/PENDING | S1、S2、S4、S5、S7、S8、S9 全部对应 | `open-decisions.md:69-110`；`business-rules.md:47-57` |

**D4 与 D9 的字面冲突及解释**：D4 的“PENDING 卡不可预约”指“有生效日、但尚未到生效日”的 PENDING（`valid_from IS NOT NULL`）；D9 的期卡 PENDING 是“有效期待定”（`valid_from IS NULL`），必须允许预约。判定函数见 `user-flow.md` 的 `is_bookable_card()`。

## 角色与权限

| 操作 | 角色/权限 | 真实现状 | F6.3 要求 |
|------|-----------|----------|-----------|
| 发放期卡 | `admin` / `super_admin` | `membership/router.py:178-179` `@require_roles("admin","super_admin")` | 不变；Service 内仍以 `current_user.tenant_id` 作为租户来源 |
| 学员预约 | `student` | `booking/router.py:22-30` | 不变；新增卡归属校验，禁止使用他人卡 |
| 完成预约 | `booking:manage` | `booking/router.py:206-213` | 不变；完成触发期卡激活，失败则整体回滚 |
| 取消预约 | 学员本人 / 管理员 | `booking/service.py:161-178` 校验 `booking.student_id == student_id` | 不变；期卡回补改为 no-op |
| 取消排期 | `schedule:cancel` | `schedule/router.py:169-186` | 不变；调用方按期卡/次卡分支回补 |
| 冻结会员卡 | 管理端 | `membership/router.py` 冻结端点（`membership/service.py:608-672`） | PENDING 必须拒绝 |
| 定时任务 | 系统（无用户态） | `main.py:77-142`；逐租户 `set_tenant_id`（`membership/scheduler.py:125-127`） | 新增任务同样逐租户设置 ContextVar；不得使用前端/LLM 传入的 tenant_id |
| 租户隔离 | 全部 | `TenantAwareRepository`（`core/base_repository.py:396-455`）、ORM 自动注入（`core/tenant_query.py:29-80`） | 卡查询必须显式 `tenant_id` + 自动注入双重约束；跨租户返回 404 或 403，不泄露存在性 |

## Dependencies

- F4.1（booking→membership_card FK `ON DELETE SET NULL`）：`booking/models.py:52-56`，已 DONE。
- F4.4（status Check 约束）：`booking/models.py:66-70`、`membership/models.py:227-231`，已 DONE。
- F2.3（签到/完成行锁）：`booking/service.py:305-332`，已 DONE。
- F2.4（取消排期回补回滚）：`schedule/service.py:304-403`，已 DONE。
- F4.5（排期创建并发）：`schedule/repository.py` 的容量递增，已 DONE。
- F6.0 决策 D1/D4/D5/D9 已冻结：`docs/features/F6.0-membership-card-prototype/open-decisions.md:7-9,134-143`。
- 运行依赖：PostgreSQL（`SELECT ... FOR UPDATE`）、Redis（`require_permissions` 缓存，`core/rbac/decorator.py:99-152`）。
- 无未完成的前置 Feature（`docs/delivery/feature-backlog.md:442`）。

## Risks

| ID | 风险 | 影响 | 缓解 |
|----|------|------|------|
| R1 | 新增 `validity_days` 快照列需要迁移，与 Backlog DoR“无 DB 结构变更即可实施”不一致 | 部署窗口需执行 Alembic；回滚需 downgrade | 迁移列为可空，先回填再上线；见 `implementation-plan.md` 的 Decision/Conflict |
| R2 | 两张 PENDING 期卡在相近排期并发预约时，二者有效期均为 NULL，无法在预约阶段互相判重叠 | 完成时第二张激活冲突 | 基线策略：激活冲突 fail-closed，事务回滚并在下一轮重试；冲突卡最终过期后重试成功；见 UNKNOWN-1 |
| R3 | 小程序把所有 PENDING 卡置灰（P19） | 后端已支持但 UI 仍不可选期卡 | 运行时验收走 API/直接构造数据；UI 联调归 F6.10/F6.11 |
| R4 | finalize 采用 fail-closed，激活异常会导致排期每 5 分钟重试并持续告警 | 运维噪音；排期长期不 FINISHED | 日志带 tenant/schedule/card；配置缺失属于部署错误，需在发布检查中拦截 |
| R5 | 历史 PENDING 卡可能带 `valid_from/expire_at`（旧发卡逻辑） | 与 D9 新语义并存 | 判定函数显式区分“有生效日的 PENDING”和“有效期待定的 PENDING”；旧卡继续由 `auto_activate` 处理（`membership/scheduler.py:136-141`） |
| R6 | `issue_card` HTTP 入口无幂等键 | 重复点击生成多张 PENDING 期卡 | 本 Feature 不扩接口；管理端按钮防抖 + 后续补幂等键 |
| R7 | `cancel_schedule` 只处理 BOOKED | 已 CHECKED_IN 的预约在排期取消时不回补 | 记录为 P17；不在本 Feature 扩大范围 |
| R8 | 卡归属/适用性校验是既有安全缺口（P14） | 修复后可能拒绝历史上“前端允许、后端未校验”的请求 | 发布前用真实数据抽样核对；错误码使用 403/400 且不泄露卡信息 |
| R9 | 以排期日替代 `now` 校验有效期会改变次卡行为 | 到期日前的未来课程可能由“可用”变为“不可用” | 这是 D4 的正确语义；上线说明中单列行为变更 |
| R10 | `ScheduleStatus` 无 COMPLETED，容易误加枚举 | 迁移/数据不一致 | 设计明确只使用 FINISHED；完成触发点是 BookingStatus |
| R11 | 90 天任务按 `created_at` 判定，若历史数据 `created_at` 缺失/异常会误作废 | 误伤合法卡 | 查询附加 `status=PENDING AND card_type=period`；上线前统计待处理数量并 dry-run |
| R12 | 同一张 PENDING 期卡的多次预约若不设窗口锚点，短有效期卡（如 7 天）可能把第二笔排到有效期外 | 首次激活后第二笔课无有效卡覆盖 | T6.3.2 以最早非取消预约排期日为锚点，后续预约必须在 `锚点 + validity_days - 1` 内 |

## UNKNOWN

1. **UNKNOWN-1 激活冲突的最终处置**：D9 只规定“预约时冲突拒绝”，未规定“并发导致激活时冲突”是回滚、保 PENDING 还是作废卡。本文基线采用 fail-closed（回滚、保 PENDING、下轮重试），需产品负责人在实现前确认；若改为“booking 完成 + 卡作废”，需新增审计与补偿规则。
2. **UNKNOWN-2 “90 天无完成记录”的计时起点**：本文按 `membership_cards.created_at`（发卡时间）计算；若产品要求“首次预约时间”或“最后一个完成排期时间”，需改查询字段。真实表无 `first_used_at` 字段（`membership/models.py:146-239`）。
3. **UNKNOWN-3 `validity_days` 的回填口径**：历史期卡可能同时存在 `product.validity_days`、`valid_from/expire_at` 和显式入参三种来源；迁移需先统计冲突数据，本文只给出优先级建议（product → 日期差反推 → NULL）。
4. **UNKNOWN-4 NO_SHOW 是否等同 COMPLETED 触发激活**：D5 文字为“课开即扣/激活”，本文按“是”；若产品认为缺席不激活，需要改 finalize 分支。
5. **UNKNOWN-5 期卡 `max_weekly_usage` 是否在预约时校验**：当前扣次路径未实现该规则（`membership/service.py:1328-1403` 无周使用上限判断），F6.3 不新增；需确认是否属于 F6.3 遗漏。
6. **UNKNOWN-6 历史 PENDING 期卡的兼容策略**：旧发卡逻辑产生的“带 `valid_from` 的 PENDING 期卡”是否继续由 `auto_activate` 直接激活（不经首次完成）。本文建议保留，避免改变既有数据语义。
7. **UNKNOWN-7 迁移执行环境**：当前未读取 `apps/api/alembic/versions` 的具体链路与生产迁移窗口；实施前需 database-engineer 复核。
8. **UNKNOWN-8 period 下 `valid_from` 入参的处理**：`MembershipCardCreate` 允许传 `valid_from`（`membership/schemas.py:121-123`），但 D9 期卡发卡应无有效期。本文建议“忽略并记录 warning”，不直接 400，以免现有管理端表单默认值导致发卡失败；需确认管理端是否总是发送该字段。
