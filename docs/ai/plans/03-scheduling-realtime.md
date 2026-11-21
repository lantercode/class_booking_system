# P3｜调度与实时推送落地计划

> 设计依据：[scheduling-and-realtime-plan.md](../architecture/scheduling-and-realtime-plan.md)。
> 原则：状态由数据派生；定时器只做副作用；推送只推变更信号。

## 阶段 0：状态纯派生（先做，风险最低）

| # | 任务 | 文件 | 验收 |
|---|---|---|---|
| 0.1 | 梳理「哪些状态字段其实可由时间推导」，列出清单 | 本文档附录 | 清单确认 |
| 0.2 | 排期展示状态改为按 `start_at/end_at` 派生，不依赖 `status` 字段的实时性 | `modules/schedule/service.py` | 停掉扫描后展示仍正确 |
| 0.3 | 预约 `display_status` 已实现时间优先，补充边界测试 | `modules/booking/service.py`、测试 | 边界：正好等于 now |
| 0.4 | 会员卡读路径：读到过期卡时做条件更新（幂等） | `modules/membership/service.py` | 重复调用不产生副作用 |

**验收**：关闭 APScheduler 中的对应 job，接口返回的状态仍与时间一致。

**风险**：派生逻辑分散到多处会不一致——统一收敛到一个函数（如 `derive_schedule_state(start_at, end_at, now)`）。

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

## 阶段 2：迁移会员卡任务

| # | 任务 | 原实现 | 新实现 |
|---|---|---|---|
| 2.1 | 卡激活 | `auto_activate_membership_cards` | 入队 → 消费；读路径 A 兜底 |
| 2.2 | 卡过期 | `auto_expire_membership_cards` | 读时条件更新（A）+ 每日对账任务 |
| 2.3 | 到期提醒 | `notify_expiring_membership_cards` | 每日按租户生成幂等任务 |
| 2.4 | 解冻 | `auto_unfreeze_membership_cards` | 延迟任务（`unfreeze_at`） |
| 2.5 | PENDING 超期作废 | `auto_cancel_pending_membership_cards` | 延迟任务 |

**迁移方式**：新旧并存，按 job 类型开关灰度；对比期记录两边结果，确认一致后关闭旧扫描。

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

## 阶段 5：前端接入

| # | 任务 | 文件 | 验收 |
|---|---|---|---|
| 5.1 | 管理端 SSE 客户端（自动重连、退避） | `apps/admin-web/src/` | 断网恢复后自动续订 |
| 5.2 | 小程序 WebSocket 客户端（`uni.connectSocket`） | `apps/miniapp/src/` | 前后台切换可重连 |
| 5.3 | 收到信号后按 `type` 拉取详情 | 各端 | 不依赖推送体内容 |
| 5.4 | 长轮询兜底（可选） | 各端 | 流式被代理阻断时可用 |

## 阶段 6：降级旧调度

| # | 任务 | 验收 |
|---|---|---|
| 6.1 | APScheduler 仅保留每日对账 job | 其余 job 全部关闭 |
| 6.2 | 对账：比对「派生状态」与「落库状态」，输出差异 | 差异为 0 |
| 6.3 | 观察两周后移除旧代码 | 无回归 |

## 附录：状态派生清单（阶段 0 产出）

| 实体 | 字段 | 派生方式 |
|---|---|---|
| 会员卡 | 是否过期 | `expire_at <= now()` |
| 会员卡 | 是否未生效 | `valid_from > now()` |
| 排期 | 是否已结束 | `end_at <= now()` |
| 排期 | 是否进行中 | `start_at <= now() < end_at` |
| 排期 | 是否可取消 | `now() < start_at - cancel_before_minutes` |
| 预约 | 展示状态 | 时间优先，其次 `booking.status` |

## 风险

| 风险 | 应对 |
|---|---|
| 双执行 | 幂等键 + 按类型灰度 + 对账 |
| 时区混用 | 统一 `timestamptz`，派生函数只比较绝对时间 |
| 队列积压 | 监控 pending 数与最老任务延迟 |
| SSE 被缓冲 | Nginx 关闭 buffering |
| 小程序 socket 域名未配置 | 部署前在微信后台登记 |
