# F4.5 — 排期创建并发安全 · 需求文档

> Feature ID：F4.5
> 作者：主控（内置总控）联合 backend / database 双域规则清单核对
> 日期：2026-10-02
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`（单模块事务安全，后端事务边界 + 数据库隔离级别双域；不动 Router / 契约 / 前端 / MCP）
> 依赖：无新外部依赖；复用既有 `ScheduleRepository.find_conflicts(use_lock=...)` 与 `course_schedules` 表
> 前置 Feature：F4.4（status Check 约束，已完成；当前 alembic head = `f44ab1c2d3e4`，本 Feature 无 migration）
> 评审修订：双专家评审后创建路径冲突检查确定为 `use_lock=False`（SERIALIZABLE 快照谓词读），原因见 Background 与 implementation-plan.md 实证 D / D2′

---

## Goal

并发创建排期时不产生时间冲突（同一教师、同一教室时间段重叠）的排期。

`ScheduleService.create_schedule` 原先的流程是"先 `find_conflicts` 检查冲突 → 无冲突再 `insert`"两步，**两者不在一个具备快照隔离保证的事务策略内**：当两个创建请求并发执行、且目标时间段原本**没有任何排期行**时，两边的冲突检查都会读到空集，于是都执行插入，最终同一教师/教室在同一时间段出现两条 NORMAL 排期。仅靠默认的 READ COMMITTED + `SELECT ... FOR UPDATE SKIP LOCKED` 无法拦截此场景（空结果集上没有任何行可锁，行锁等价于无锁）。

**评审阶段还发现第二类漏判（实证 D）**：当冲突排期 S **已存在**、但正被另一个 READ COMMITTED 事务（预约 `increment_booked_count` / 取消 `decrement_booked_count` 持 schedule 行锁）锁定时，创建事务中的 `FOR UPDATE SKIP LOCKED` 会把这条真实冲突行**直接跳过** → 误判空集 → 插入重叠行；锁方为 RC 不产生 SIREAD 锁，SSI 依赖图缺边，`40001` 不会触发，形成静默双占。因此创建事务的冲突检查必须使用普通快照谓词读（`use_lock=False`），不得带 `SKIP LOCKED`。

修复目标（对应 backlog 的 T4.5.1 与 T4.5.2，二者同时采用）：

1. **同事务**：冲突检查 `find_conflicts` 与插入 `repo.create` 放入同一个数据库事务；
2. **SERIALIZABLE**：把该创建事务的隔离级别提升为 `SERIALIZABLE`，由 PostgreSQL SSI（可序列化快照隔离）的谓词锁在提交时检测"两个事务都读空集后插入同一时间段"的危险结构，让其中一个事务收到 SQLSTATE `40001`（SerializationFailure）；
3. **重试与兜底**：Service 捕获 `40001` 自动以新快照重跑（最多 3 次）；重试耗尽返回友好业务错误，绝不向前端透传 traceback / SQL。
4. **快照谓词读（评审修订）**：创建事务内冲突检查固定 `use_lock=False`——已提交冲突行由快照读确定性可见，空集双插由 SSI 兜底；杜绝 `SKIP LOCKED` 吞掉被并发 RC 事务持锁的真实冲突行。

## User Story

作为排课管理员，
我希望在我和另一位管理员（或同一时间的重复提交）并发创建同一教师/教室的重叠排期时，有且仅有一个成功，另一个收到明确的"时间冲突 / 请稍后重试"提示，以便系统不会出现两条互相冲突的排期。

作为排课管理员，
我希望并发创建两条时间不重叠的排期时两者都成功，不被过度加锁误伤，以便正常的批量操作不被拖慢。

作为系统，
我希望并发可序列化冲突（`40001`）对用户表现为有限次自动重试 + 最终友好错误，而不是 500 traceback，以便偶发并发冲突可自愈、极端冲突可理解。

作为运维 / DBA，
我希望该事务方案不依赖非官方的裸 SQL 技巧、不在 PostgreSQL 日志产生 WARNING，并对隔离级别是否真实生效有可验证的证据，以便方案可审计、可迁移。

## Background / 现状（已核查的代码与 DB 事实）

| 事实 | 证据 |
|------|------|
| `create_schedule` 原先"检查→插入"两步、无 SERIALIZABLE、无重试 | `git show HEAD` 版本：`find_conflicts(..., use_lock=True)` 后直接构造冲突错误，随后 `repo.create`；无隔离级别提升、无 try/重试 |
| `find_conflicts(use_lock=...)` 已存在（**非本 Feature 新增**），`use_lock=True` 时对教室/教师冲突查询加 `.with_for_update(skip_locked=True)` | [repository.py:114-181](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/repository.py#L114-L181)；方法逻辑 HEAD 逐行一致，本 Feature 仅补 docstring 警告；**创建路径最终传 `use_lock=False`（D2′）** |
| 空集上的 `FOR UPDATE SKIP LOCKED` 在 READ COMMITTED 下不能阻止并发双插 | 本 Feature 因果对照实验（见 implementation-plan.md 实证 B / D1）：双连接 RC + 同逻辑，两事务都读空集后插入 → **2 行** |
| SERIALIZABLE + SSI 能拦截"空集双插"（纯 SELECT / FOR UPDATE / SKIP LOCKED 三种写法在该场景均 1 行） | 同对照实验：SERIALIZABLE 下 1 个提交成功、另一个 COMMIT 时收到 `40001`，最终 **1 行**。**但该实验不覆盖"已存在且被持锁的冲突行"**——实证 D 证明该场景下 SKIP LOCKED 会漏判且 40001 不兜底，故最终选用普通快照谓词读 |
| 冲突判断双维度：同教室 `classroom_id` 或同教师 `teacher_id`，时间谓词 `start_at < end AND end_at > start`，且仅 NORMAL | [repository.py:129-161](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/repository.py#L129-L161) |
| 租户谓词由 `get_tenant_id()`（ContextVar）注入 `find_conflicts` | [repository.py:127-137](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/repository.py#L127-L137)（符合 tenant-isolation.md，租户身份取自可信上下文而非入参） |
| 表已有教师/教室时间索引（SSI 谓词锁可落在索引） | [models.py:75-78](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/models.py#L75-L78)：`idx_schedules_teacher_start` / `idx_schedules_classroom_start` |
| 无 schema 变更需求；当前 head `f44ab1c2d3e4`（F4.4） | 本 Feature 只改 Service 事务行为 + 新增集成测试；不新增列/约束/索引，故**无 migration** |
| 同模块批量创建 `batch_create_schedules` 仍是旧模式（行锁但非 SERIALIZABLE） | [service.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py) `batch_create_schedules`；backlog Scope 仅要求单个 `create_schedule`，列入 Out of Scope / UNKNOWN |

## Scope（In Scope）

1. 改造 [service.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py) 的 `ScheduleService.create_schedule`：
   - 纯无状态校验（时间范围、预约开放/截止、取消截止、教室存在/可用）放在重试循环外；
   - 循环内先 `rollback` 关闭上游（认证 / RBAC 依赖）可能已开启的只读事务，再通过官方入口 `db.connection(execution_options={"isolation_level": "SERIALIZABLE"})` 把本次创建事务提升为 SERIALIZABLE；
   - 同一事务内 `find_conflicts(use_lock=False)`（**评审修订**：普通快照谓词读；理由见实证 D / D2′）→ 有冲突 `rollback` + `BusinessException(400)`；无冲突 `repo.create(auto_commit=False)` + `commit`；
   - 新增 `_is_serialization_failure`（识别 SQLSTATE `40001` / `"could not serialize access"`）与常量 `_CREATE_SERIALIZABLE_MAX_ATTEMPTS = 3`；
   - `40001` 自动重试（最多 3 次），耗尽或其他异常 → `BusinessException(500)` 友好文案；`BusinessException` 直接上抛不重试。
2. 修正 `ScheduleRepository.find_conflicts` 的 docstring（仅注释，补充 `SKIP LOCKED` 会跳过被持锁冲突行的警告；**方法逻辑零改动**）。
3. 新增集成测试 `tests/integration/test_schedule_create_concurrency.py`（**9 用例**，真实 asyncpg + 真实 PostgreSQL，双独立 session + `asyncio.gather` 模拟并发；含评审回归 `TestLockedConflictRowNotSkipped`）。

## Out of Scope

- 不改 `ScheduleRepository.find_conflicts` 的方法逻辑与 SQL 谓词（`use_lock` 开关 / 谓词均为既有），不新增 Repository 方法。
- 不改 Router / schemas / OpenAPI（HTTP 端点签名与响应结构不变，仅并发语义增强）。
- 不新增 migration / 列 / 约束 / 索引（不改 DB schema）。
- 不引入排他约束（`EXCLUDE USING gist`）/ `btree_gist` 扩展（更强但超出 backlog 指定的事务方案，留待评估，见 UNKNOWN U3）。
- 不改造 `batch_create_schedules`（backlog 仅要求单个 `create_schedule`，见 UNKNOWN U2）。
- 不改前端 4 端 / MCP / Redis。
- 不回滚、不纳入工作区中与本 Feature 无关的预存改动（`repository.py` 内 `increment_booked_count` 的 `with_for_update(skip_locked=True)`，属预约抢名额并发，见 UNKNOWN U4；注意本 Feature 也会触碰同一文件的 `find_conflicts` docstring，提交时按 hunk 区分，只 stage docstring hunk）。

## Acceptance Criteria（摘要，详见 acceptance.md）

- AC-1：并发创建时间重叠排期（完全重叠 / 部分重叠）→ 恰好一个成功，另一个 `BusinessException(400)`，DB 仅 1 行。
- AC-2：并发创建时间不重叠排期 → 两者都成功，DB 2 行。
- AC-3：一次性 `SerializationFailure(40001)` 被捕获并重试，第二次以新快照成功落库（共 2 次尝试）。
- AC-4：持续 `40001`、重试耗尽（3 次）→ 友好 `BusinessException`（文案含"重试"），不透传 traceback，0 行落库。
- AC-5：串行行为不回归（串行冲突仍 400、合法创建成功、非法时间参数在事务外被 `ValidationException` 拦截）。
- AC-5b（评审新增）：冲突排期 S 已存在且正被并发 RC 事务 `SELECT ... FOR UPDATE` 持锁时，创建重叠排期仍被确定性拒绝（`BusinessException(400)`、窗口内仅 1 行），不被 `SKIP LOCKED` 吞掉。
- AC-6：事务真实运行在 SERIALIZABLE（有 SHOW + SSI 实证，非静默 READ COMMITTED）。
- AC-7：分层 / 租户 / 异常处理合规（事务边界在 Service；复用既有 Repository；租户取自 ContextVar；无 SQL/traceback 泄漏）。
- AC-8：回归不破坏 F4.1 / F4.2 / F4.4 及 schedule delete / cancel / scheduler 既有测试。

## Dependencies

- 复用：既有 `course_schedules` 表及其教师/教室时间索引；既有种子数据（`dance-school` 租户 + 种子教师 13800138001 + 既有 course，conftest 初始化）。
- 复用：既有 `ScheduleRepository.find_conflicts` / `create`；既有 `BusinessException` / `ValidationException` / `NotFoundException` 统一异常体系。
- 无新外部依赖；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响；无 migration。
- SQLAlchemy 2.0 `AsyncSession.connection(execution_options=...)` 为官方支持的事务隔离级别设置入口（已在当前安装版本实测可用）。

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 生产真实并发量下 SERIALIZABLE 的 `40001` 触发率与重试后失败率 | dev 无法压测；排期创建是低频管理写、冲突窗口极小，3 次重试足够；即使耗尽也只返回友好错误、不产生脏数据。建议生产对 `SerializationFailure` 重试日志加监控 |
| U2 | `batch_create_schedules` 未包 SERIALIZABLE（仍 RC + FOR UPDATE） | backlog Scope 仅 `create_schedule`；批量导入通常单管理员串行触发、空集双插概率低，但理论同类窗口存在 → 另立 Feature 评估，不在本 Feature 顺手扩 |
| U3 | 是否应以 DB 排他约束（`EXCLUDE USING gist` + `btree_gist`）替代/叠加 SERIALIZABLE | 排他约束是更强的库内最终保证，但需扩展与多列（tenant+teacher / tenant+classroom + 时间范围）约束设计，超出 backlog；当前事务方案已满足"并发不产生冲突排期"，留待未来专项 |
| U4 | 工作区预存改动 `increment_booked_count` → `with_for_update(skip_locked=True)` | 与本 Feature 无关（预约抢名额并发，非排期创建）；不回滚、不纳入本 Feature 改动面；提交 F4.5 时 stage `schedule/service.py`、`schedule/repository.py` 中**仅 docstring hunk** 与新增测试文件，skip_locked hunk 不 stage |
