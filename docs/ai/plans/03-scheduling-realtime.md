# P3｜调度与实时推送落地计划

> 设计依据：[scheduling-and-realtime-plan.md](../architecture/scheduling-and-realtime-plan.md)。
> 原则：状态由数据派生；定时器只做副作用；推送只推变更信号。

## 阶段 0：状态纯派生（2026-11-24 完成）

| # | 任务 | 产出 |
|---|---|---|
| 0.1 | 梳理状态派生清单 | 本文档附录（基于真实代码复核） |
| 0.2 | 排期 display_status 收敛为纯函数 `derive_schedule_display_status` | `modules/schedule/service.py` |
| 0.3 | 会员卡有效状态收敛为纯函数 `derive_card_effective_status` | `modules/membership/service.py` |
| 0.4 | 预约 `display_status` 时间优先逻辑保持不变（已在 service.py L1458-1499 实现） | 无需改动 |

**测试覆盖**：3 个纯函数共 35 条边界测试（排期 12、会员卡 13、预约 10），全部通过。

**实现说明**：

- 三个纯函数都支持传入 `now` 参数（默认 `datetime.now(UTC)`），精确控制时间边界；
- 排期的 `display_status`：`_to_response` 统一调 `derive_schedule_display_status`，DB `status=FINISHED` 仅是业务写入（可退化为每日对账），展示正确性完全由时间保证；
- 会员卡的 `effective_status`：读路径（`get_card` 等）可直接调用；过期优先 → FROZEN 冻结期内 → ACTIVE/PENDING 时间派生；
- scheduler 的裸写 debt（`auto_activate` L200、`auto_unfreeze` L515 绕过 Service 层直接写 `card.status=ACTIVE`）**P3-2 阶段统一收口**——迁到 job_queue 时改调 service 层 `activate_card` / `unfreeze_card`。P3-0 阶段只加派生函数，不碰 scheduler 副作用逻辑。

## 阶段 1：job_queue + Worker

| # | 任务 | 文件 | 验收 |
|---|---|---|---|
| 1.1 | 新增迁移：`job_queue` 表（含 `idempotency_key` 唯一索引、`run_at`、`status`、`attempts`、`locked_by`） | `alembic/versions/` | 迁移可升可降 |
| 1.2 | Repository：入队、抢任务（`FOR UPDATE SKIP LOCKED`）、标记完成/失败 | `modules/task/`（新增模块） | 并发抢不重复 |
| 1.3 | Worker：独立进程或独立 asyncio 任务，带租约超时回收 | `apps/api/src/app/worker.py`（新增） | 进程被杀后任务可被重新领取 |
| 1.4 | 退避重试与死信（attempts 上限） | 同上 | 失败 3 次进 dead |
| 1.5 | 单测：并发抢锁、幂等、重试、租约回收 | `tests/unit/test_task_queue.py` | 全绿 |

**验收**：同一 `idempotency_key` 入队两次，只执行一次；起 2 个 worker 不重复执行。

**注意**：worker 必须使用**独立 AsyncSession**，禁止与 API 请求共享。

**实现说明（2026-11-24 完成）**

- Worker 落在 `modules/task/`（非原计划的 `app/worker.py`），以 asyncio 任务随应用 lifespan 启停，`TASK_WORKER_ENABLED=false` 默认关闭；
- `enqueue` / `claim` 全部使用原生 SQL（`FOR UPDATE SKIP LOCKED` CTE + `ON CONFLICT DO NOTHING`），避免 ORM identity map 破坏同事务内 CTE 可见性；
- 首个调度侧试点：`send_renewal_alerts` 在 `TASK_WORKER_ENABLED=true` 时改为入队 `notify_renewal_alert`，否则保持同步直发（灰度开关，避免 Worker 未启动导致告警丢失）；入队键按天去重，通知侧幂等键保证同一卡同一周期只发一条；
- 单测：`tests/unit/test_task_queue.py`（并发抢锁、幂等、租约回收、重试上限、终态、调度入队/直发双路径），全量 288 passed。

## 阶段 2：迁移会员卡任务

| # | 任务 | 原实现 | 新实现 |
|---|---|---|---|
| 2.1 | 卡激活 | `auto_activate_membership_cards` | 入队 → 消费；读路径 A 兜底 |
| 2.2 | 卡过期 | `auto_expire_membership_cards` | 读时条件更新（A）+ 每日对账任务 |
| 2.3 | 到期提醒 | `notify_expiring_membership_cards` | 每日按租户生成幂等任务 |
| 2.4 | 解冻 | `auto_unfreeze_membership_cards` | 延迟任务（`unfreeze_at`） |
| 2.5 | PENDING 超期作废 | `auto_cancel_pending_membership_cards` | 延迟任务 |

**迁移方式**：新旧并存，按 job 类型开关灰度；对比期记录两边结果，确认一致后关闭旧扫描。

**实现进度**

- 2.1 卡激活（2026-11-24 完成）：
  - 裸写逻辑收口为 `MembershipCardService.auto_activate_card`（行锁 + 状态重检 + 冲突跳过 + ISSUE 流水），不再直接改 `card.status`；
  - scheduler 扫描候选后：`TASK_WORKER_ENABLED=true` 入队 `activate_membership_card`（按天幂等键），否则同线程直接调 Service；
  - Worker handler 在无租户 ContextVar 环境下可完成激活（产品快照回退使用显式 tenant 查询）；
  - 测试：`tests/unit/test_card_auto_activate.py`（Service 4 条 + scheduler 双路径 2 条 + handler 1 条）。
- 读路径 A 兜底（2026-11-25 完成）：`MembershipCardResponse` 增加 wrap 校验器，所有返回会员卡的接口统一使用 `derive_card_effective_status` 派生状态（PENDING 到点显示 ACTIVE、超期显示 EXPIRED、冻结到期显示 ACTIVE、CANCELLED 不可覆盖）；naive datetime 不做派生以免比较异常。测试：`tests/unit/test_card_response_derived_status.py`。
- 2.2 卡过期（2026-11-25 完成）：
  - 状态流转保持走 `MembershipCardService.expire_card`（行锁 + 状态重检 + 次卡清零流水，幂等）；
  - scheduler：`TASK_WORKER_ENABLED=true` 入队 `expire_membership_card`（按天幂等键），否则同线程直接调 Service；
  - `_expire_cards_in_transaction`（激活前预处理）仍同步执行，属事务内前置条件，不做队列化；
  - 测试：`tests/unit/test_card_expiry_migration.py`（入队 / 直接过期 / handler 无 ContextVar + 幂等）。
- 2.3 到期提醒（2026-11-25 完成）：由「仅打日志」升级为幂等站内提醒（同一卡同一到期日一条）；`TASK_WORKER_ENABLED=true` 入队 `notify_card_expiring`，否则直发 NotificationService。
- 2.4 自动解冻（2026-11-25 完成）：
  - 裸写收口为 `MembershipCardService.auto_unfreeze_card`（行锁 + 状态/时间重检 + 冲突保持冻结并更新原因 + 有效期按 `frozen_remaining_days` 顺延 + 回填冻结记录 `unfrozen_at`）；
  - scheduler 入队 `unfreeze_membership_card` 或直接调 Service；
  - 移除 `MembershipCardRepository` / `MembershipCardFreeze` 的调度侧直接使用。
- 2.5 PENDING 期卡作废（2026-11-25 完成）：原逻辑已走 Service；补 `TASK_WORKER_ENABLED` 双路径，入队 `cancel_pending_membership_card`（payload 含 `card_id` / `days`），Worker 执行时经 BookingService 重新校验「是否已使用」再作废。
- 阶段 2 测试汇总：`tests/unit/test_card_jobs_migration.py`（2.3/2.4/2.5 共 8 条）；`pytest tests/unit tests/test_scheduler_tenant_isolation.py` → 322 passed。

**验收**

- 关闭旧 job 后，卡状态变化仍准点；
- 同一卡不会重复扣次/重复作废；
- 停机 10 分钟恢复后，错过的任务被补执行。

## 阶段 3：迁移排期任务（延迟任务）

| # | 任务 | 触发时机 | 幂等键 |
|---|---|---|---|
| 3.1 | 课程结束自动完成 | 排期创建时投递 `end_at + grace` | `schedule:{id}:complete` |
| 3.2 | 人数不足自动取消 | 排期创建与每次预约变更时重投递 `start_at - cancel_before` | `schedule:{id}:cancel_underbooked` |
| 3.3 | 排期变更时撤销旧任务 | 修改时间/取消排期 | 同上，覆盖 `run_at` |

**验收**：只有真正到点的排期被处理，不再全表扫描；重复投递不重复执行。

**实现说明（2026-11-25 完成）**

- 新增 `modules/schedule/jobs.py`：`sync_schedule_jobs` 在排期 NORMAL 时投递两类延迟任务——`finish_schedule`（`run_at = max(end_at + grace, now)`）与 `cancel_schedule_if_underbooked`（`run_at = max(start_at - cancel_before, now)`，`cancel_before` 取课程类型的 `cancel_before_minutes`）；已存在的任务用 `upsert` 覆盖 `run_at`，非 NORMAL 排期直接返回；
- 投递统一走 `safe_sync_schedule_jobs`（savepoint 包裹 + 独立 commit），投递失败只记日志，不污染业务事务、不影响返回对象；
- 接线：`create_schedule` / `update_schedule` 提交后 sync；`cancel_schedule` 调 `cancel_schedule_jobs` 撤销两个键；
- 预约变更：`create_booking`、`_do_cancel_booking` 提交后重投递 `cancel_underbooked`（人数变化会改变取消判定）；
- Worker handlers：`finish_schedule` 重查租户/状态/到点条件后调 `BookingService.finalize_schedule_bookings`；`cancel_schedule_if_underbooked` 用 join 重查 `status/booked_count/start_at/min_students/cancel_before`，达标跳过、未到 deadline 则 upsert 顺延、到点调 `ScheduleService.cancel_schedule` 且 `operator_id=0`；
- 测试：`tests/unit/test_schedule_jobs_migration.py`（5 条）。

## 阶段 4：后端推送通道

| # | 任务 | 文件 | 验收 |
|---|---|---|---|
| 4.1 | 确定鉴权方式（Cookie 还是 fetch 流式） | 决策记录 | 明确写进文档 |
| 4.2 | SSE 端点：按 `tenant_id + user_id` 订阅，心跳保活 | `modules/notify/`（新增） | 浏览器可收到事件 |
| 4.3 | WebSocket 端点：JWT 握手、心跳、断线清理 | 同上 | 小程序可收 |
| 4.4 | 事件发布：业务提交后（Outbox）发布 `{type, entity_id, version}` | `modules/notify/service.py` | 只推信号不推数据 |
| 4.5 | Nginx 配置：`proxy_buffering off` | `infra/nginx/` | 事件不被缓冲 |
| 4.6 | 限流：单用户连接数与消息速率 | `middleware/` | 超限断开 |

**验收**：状态变更后 1 秒内前端收到信号；断线重连后能通过 HTTP 补齐。

**实现说明（2026-11-25 完成）**

- **4.1 鉴权决策**：Web 三端登录态是 localStorage 里的 Bearer Token（不走 Cookie），`EventSource` 无法自定义请求头，因此 **SSE 采用 `fetch` + `ReadableStream` + `Authorization` 头**；小程序 WebSocket 无法自定义头，**token 走 query**（`/notify/ws?token=`）。两种方式都在握手期完成认证与黑名单校验，`tenant_id/user_id` 只从可信 Token 取，不接受前端传入。
- 4.2 SSE：`GET /api/v1/notify/stream`，`Depends(get_current_user)`，首帧 `retry: 3000`，`NOTIFY_HEARTBEAT_SECONDS`（默认 25s）无事件时发 `: ping`，`finally` 退订并释放配额；响应头含 `X-Accel-Buffering: no`。
- 4.3 WebSocket：`WS /api/v1/notify/ws?token=`，`decode_token` + `is_token_blacklisted` 失败分别 close 4401/1011，超限 close 4429；心跳消息 `{"type":"ping"}`。
- 4.4 事件发布：`publish_change(tenant_id, user_id, type, entity_id, version=1)` → Redis channel `notify:events`，各实例监听器收到后分发到本进程订阅队列；`user_id=0` 表示租户内广播（管理端）。事件体只含 `type/entity_id/version`，不含业务数据。已接线：排期取消、预约创建、预约取消。预约事件同时发布两份：定向给学员本人（`booking.created` / `booking.cancelled`）与租户广播（`booking.changed`），后者供管理端/教师端刷新列表（联调发现仅定向时管理端收不到预约事件，2026-11-25 补齐）。
- 4.5 Nginx（2026-11-26 完成）：`infra/nginx/nginx.conf`（生产 admin / api 两个 server）与 `infra/nginx/nginx.stage-a.conf` 均新增两个专用 location：
  - `location = /api/v1/notify/stream`：`proxy_buffering off`、`proxy_cache off`、`gzip off`、`proxy_http_version 1.1`、`proxy_read_timeout 3600s`，保证事件即时下发；
  - `location = /api/v1/notify/ws`：透传 `Upgrade` / `Connection "upgrade"`，供小程序 WebSocket 使用。
  - 后端 `X-Accel-Buffering: no` 保留为双保险；`proxy_read_timeout` 远大于心跳 25s，避免空闲断连。
- 4.6 限流：单用户连接配额（`NOTIFY_MAX_CONNECTIONS_PER_USER`，默认 3，SSE 超限 429 / WS 超限 4429）；消息速率限制（2026-11-26 完成）按 `(tenant_id, user_id)` 做 1 秒窗口限流，默认 `NOTIFY_MAX_EVENTS_PER_SECOND=20`（`<=0` 关闭），`user_id=0` 的租户广播按租户单独计数；超限**丢弃信号**而非断开连接（信号可凭 HTTP 补齐），连接释放后清理该用户窗口。
- 测试：`tests/unit/test_notify_bus.py`（配额、定向/广播、队列满丢弃、Redis 失败降级与成功发布、速率上限、按用户隔离、释放清理窗口）。

## 阶段 5：前端接入

| # | 任务 | 文件 | 验收 |
|---|---|---|---|
| 5.1 | 管理端 SSE 客户端（自动重连、退避） | `apps/admin-web/src/` | 断网恢复后自动续订 |
| 5.2 | 小程序 WebSocket 客户端（`uni.connectSocket`） | `apps/miniapp/src/` | 前后台切换可重连 |
| 5.3 | 收到信号后按 `type` 拉取详情 | 各端 | 不依赖推送体内容 |
| 5.4 | 长轮询兜底（可选） | 各端 | 流式被代理阻断时可用 |

**实现进度（2026-11-25）**

- 5.1 管理端 SSE 客户端：`apps/admin-web/src/utils/notify.ts`，`fetch` 流式按空行分帧，指数退避 1s→30s，提供 `connect/disconnect/onChange`；`window.online` 恢复时立即重连；401 不自行刷新（统一刷新逻辑只在 api-client 拦截器）。
- 5.2 小程序 WebSocket 客户端：`apps/miniapp/src/api/notify.ts`，`uni.connectSocket`，token/tenant_slug 走 query，`uni.onAppShow` 切回前台时重连；接口与 Web 端一致。
- **断线补齐（2026-11-26 完成）**：两端客户端新增 `onReconnect`（仅「已有过成功连接后的再次连接」触发，首次连接不触发），`notify-sync.ts` 在重连后刷新当前所有已注册通道，覆盖断线期间错过的信号；`disconnect()` / 重新 `connect()` 会重置该状态。
- **空闲看门狗（2026-11-26 完成）**：管理端 SSE 读流增加 90s 空闲超时（后端心跳 25s），超时主动 abort 并进入退避重连。原因：代理（实测 Vite）在上游断开后可能不关闭下游响应，客户端若只依赖流结束事件将永远感知不到断线。
- 重连补齐实测（2026-11-26）：页面基线 2/10 → 杀死后端连接 → 直接改库为 3/10 且不发布任何事件 → 后端恢复 → 页面未刷新/未导航自动显示 3/10，搜索条件保留；服务端日志可见重连后紧跟一次 `GET /api/v1/schedules`。
- 5.3 收到信号按 `type` 拉详情：已完成 admin-web 与 miniapp 页面级接入（2026-11-25）——
  - 连接生命周期：admin-web `App.vue` 启动有 token 即 `connect()`、`stores/auth.ts` 登录后 connect / `clearToken()` 断开；miniapp `App.vue` onLaunch 有 token connect、监听 `login-success` / `auth:cleared`，`utils/auth.ts` logout/clearAuth 断开；
  - 事件桥接：两端各新增 `notify-sync.ts`，`booking.created|booking.cancelled` → 刷新 `bookings` + `schedules` 通道，`schedule.cancelled` → 刷新 `schedules` + `bookings`，未知 type 忽略；页面在 `onMounted` 注册既有加载函数、`onUnmounted` 注销；
  - 已接入页面：admin-web 预约列表 / 点名 / 排期列表；miniapp 学员预约、学员排期、教师排期；
  - student-web / teacher-web 暂未接入（可复用同一桥接模式）。
- 5.4 长轮询兜底：未实现（项目无此需求场景，SSE 不可用时前端退化为定时刷新即可）。
- 验证：admin-web `vue-tsc` / `eslint` / `prettier` 通过；miniapp `vue-tsc` 通过。
- **端到端联调（2026-11-25，本机 8000 + 5173）**：
  - 协议级：admin 登录 → `GET /api/v1/notify/stream` → `ScheduleService.cancel_schedule` → SSE 收到 `{"type":"schedule.cancelled","entity_id":...,"version":1}`，时延 < 1s；
  - 浏览器级：排期页保持打开、不刷新/不点击查询，课程状态自动从「待上课」变为「已取消」，证明 `SSE → notify-sync → fetchSchedules` 生效；
  - 联调发现并修复：预约事件原先只定向给学员，管理端/教师端收不到 → 增加 `booking.changed` 租户广播，两端 `EVENT_CHANNELS` 已映射；
  - 预约事件联调（2026-11-26，种子学员 13900139001 真实下单/取消）：学员 SSE 收到 `booking.created` + `booking.changed`，管理端 SSE 仅收到 `booking.changed`；取消后学员收到 `booking.cancelled` + `booking.changed`，管理端再次收到 `booking.changed`；全程管理端未收到任何定向事件。临时课程/排期/会员卡/预约/流水/job 已清理（残留 0）。

## 阶段 6：降级旧调度

| # | 任务 | 验收 |
|---|---|---|
| 6.1 | APScheduler 仅保留每日对账 job | 其余 job 全部关闭 |
| 6.2 | 对账：比对「派生状态」与「落库状态」，输出差异 | 差异为 0 |
| 6.3 | 观察两周后移除旧代码 | 无回归 |

**实现进度（2026-11-25）**

- 6.1 完成：`main.py` 在 `TASK_WORKER_ENABLED=true` 时，注册完所有 job 后移除除 `reconcile_derived_status` 外的全部旧扫描任务；`false` 时保持现有行为（灰度）。
- 6.2 完成：`modules/common/reconcile.py` 的 `reconcile_derived_status` 每日运行，逐租户只读比对四类差异（排期未完成 / 卡未过期 / 卡未激活 / 卡未解冻），输出统计并打印告警，不修改数据。
- 6.3 **未执行**：需生产观察两周且 6.2 差异为 0 后才能删除旧扫描代码，本次仅保留旧代码作为灰度回退路径。

## 附录：状态派生清单（阶段 0 产出 · 2026-11-24 基于真实代码复核）

> 判定原则：DB 字段 = "业务语义"（保留写入）；派生状态 = "展示正确性"（时间优先覆盖）。

| 实体 | DB 字段 | 派生方式 | 来源代码 | 是否可停对应定时 job |
|---|---|---|---|---|
| 排期 | `display_status` | `start_at/end_at` 与 `now` 比较；时间已过即 4 | `schedule/service.py` `_to_response` L704-752 | —（已派生） |
| 排期 | `status=FINISHED` | 完全可由 `end_at + grace_minutes < now` 派生 | 同上 L717-721 已覆盖 | ✅ `auto_finish_expired_schedules` 降级为每日对账 |
| 排期 | `status=CANCELLED` | **不可派生**（业务取消，与时间无关） | `cancel_schedule` L401 业务写入 | ❌ 保留 |
| 会员卡 | `card.status=EXPIRED` | 可由 `expire_at < now` 派生 | `validate_card_for_booking` L614-664 已做时间检查 | ✅ `auto_expire_membership_cards` 降级（但需保留次卡清零副作用） |
| 会员卡 | `card.status=ACTIVE`（valid_from 到期自动激活） | 可由 `status=PENDING + valid_from <= now` 派生 | scheduler 裸写 debt（L200） | ⚠️ 先修裸写再接读时派生 |
| 会员卡 | `card.status=ACTIVE`（冻结到期自动解冻） | 可由 `status=FROZEN + frozen_until <= now` 派生 | scheduler 裸写 debt（L515） | ⚠️ 同上 |
| 会员卡 | `card.status=CANCELLED` | **不可派生**（超期未激活 PENDING 业务作废） | `cancel_pending_card` L1489 业务写入 | ❌ 保留 |
| 会员卡 | `card.status=FROZEN` | **不可派生**（业务冻结） | `freeze_card` L1386 业务写入 | ❌ 保留 |
| 预约 | `display_status` | 时间优先，覆盖脏数据 | `booking/service.py` `_to_response` L1458-1499 | —（已派生） |
| 预约 | `booking.status=COMPLETED/NO_SHOW` | 不可派生（行为语义：签到过 vs 未签到） | `finalize_schedule_bookings` L1057-1060 | ⚠️ 收敛为 schedule FINISHED 后 booking.status 在查询时转译，改动风险较高 |

**关键约束**

- `auto_finish_expired_schedules` 除了改写 schedule.status=FINISHED，还会级联写 booking.status=COMPLETED/NO_SHOW 并触发期卡首次激活。后两者是副作用，不可纯派生——只能让"状态正确性"不依赖定时任务，副作用仍可保留。
- `auto_expire_membership_cards` 除了写 EXPIRED，还会清零次卡 `used_credits = total_credits`。清零是副作用，读时派生 EXPIRED 后仍需决定是否保留清零定时任务。
- scheduler 中 **auto_activate (L200) 和 auto_unfreeze (L515)** 绕过 Service 层直接写 `card.status = ACTIVE`，是历史技术债；改之前先收口到 Service 层。

## 风险

| 风险 | 应对 |
|---|---|
| 双执行 | 幂等键 + 按类型灰度 + 对账 |
| 时区混用 | 统一 `timestamptz`，派生函数只比较绝对时间 |
| 队列积压 | 监控 pending 数与最老任务延迟 |
| SSE 被缓冲 | Nginx 关闭 buffering |
| 小程序 socket 域名未配置 | 部署前在微信后台登记 |
