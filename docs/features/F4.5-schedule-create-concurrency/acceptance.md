# F4.5 — 排期创建并发安全 · 验收标准

> 每条 AC 均可判定 PASS/FAIL。运行时 AC 由集成测试 `tests/integration/test_schedule_create_concurrency.py` 验证。
> 测试入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_schedule_create_concurrency.py -v`
> 并发模型：两个独立 `AsyncSession`（同一 `session_factory`、不同连接 = 两个真实 DB 事务）+ `asyncio.gather`；真实 asyncpg + 真实 PostgreSQL；数据标记 `capacity=78` + 2099 时间窗隔离，用例 finally 自清。

| # | AC | 分组 | 验证方式 | 预期 |
|---|----|------|---------|------|
| AC-1 | 并发创建时间**重叠**排期，恰好一个成功、另一个冲突业务错误、DB 仅 1 行 | 运行时/并发 | `test_concurrent_overlapping_only_one_succeeds`（完全重叠）+ `test_concurrent_partial_overlap_only_one_succeeds`（30 分钟部分重叠） | 成功=1、失败=1；失败为 `BusinessException` 且 `code==400`；窗口内 `COUNT==1` |
| AC-2 | 并发创建**不重叠**排期两者都成功 | 运行时/并发 | `test_concurrent_non_overlapping_both_succeed` | 失败=0、成功=2；两响应 `id` 不同；两窗口各 1 行 |
| AC-3 | 一次性 `SerializationFailure(40001)` 自动重试后成功 | 运行时/健壮性 | `test_serialization_failure_retried_and_succeeds`（monkeypatch 令首次 `find_conflicts` 抛 `asyncpg.SerializationError`） | 第 1 次失败、第 2 次成功（`attempts==2`）；返回 `id` 非空；窗口内 1 行 |
| AC-4 | 持续 40001、重试耗尽 → 友好业务错误，0 行落库，不透传 traceback | 运行时/健壮性 | `test_serialization_failure_exhausted_returns_business_error`（持续注入 40001） | `pytest.raises(BusinessException)`；`msg` 含"重试"；恰好 3 次尝试；窗口内 `COUNT==0`；异常类型非驱动原生异常 |
| AC-5 | 串行路径行为不回归 | 运行时/回归 | `test_serial_conflict_still_rejected` / `test_serial_valid_create_succeeds` / `test_invalid_time_range_rejected` | 串行第二次重叠→`BusinessException(400)` 且 msg 含"教师时间冲突"、窗口 1 行；合法创建字段正确（teacher/status/booked_count=0）；`end==start`→`ValidationException` |
| AC-5b | **已存在冲突行正被并发 RC 事务持行锁时仍被拦截**（评审新增） | 运行时/并发 | `test_existing_conflict_row_locked_by_rc_tx_is_still_detected`：先建 S；另一 RC 会话 `SELECT … FOR UPDATE` 持 S 不提交；同窗口分别探测 `use_lock=True/False` 后再走 Service 创建 | 持锁窗口内：`use_lock=True` 探测返回空集（固化漏判根因）、`use_lock=False` 探测可见 S；Service 创建抛 `BusinessException(400)` 且 msg 含"教师时间冲突"；窗口内始终 1 行。修复前同位置 `DID NOT RAISE`（因果对照已验证） |
| AC-6 | 创建事务真实运行在 **SERIALIZABLE**（非静默 READ COMMITTED） | 运行时/架构实证 | (a) 事务内 `SHOW transaction_isolation == serializable`（全新 session 与"有上游只读事务"两路径）；(b) 因果对照实验（`asyncio.Barrier(2)` 保证两事务都完成快照读后再插入） | 两路径 SHOW 均为 `serializable`；空集双插场景 SER 组（纯 SELECT / FOR UPDATE / FOR UPDATE SKIP LOCKED）均 1 commit + 1 `40001` + 落 1 行；READ COMMITTED 对照组双写落 2 行（注：该实验只覆盖空集竞态，持锁已存在行见 AC-5b/实证 D） |
| AC-7 | 分层 / 租户 / 异常处理合规 | 静态 | 代码审查（见 static-verification.md） | 事务边界在 Service；冲突检查（快照谓词读 `use_lock=False`）与插入同一 SERIALIZABLE 事务；复用既有 `find_conflicts`（仅补 docstring），无裸 SQL 业务读写；租户谓词取自 ContextVar；无 SQL/traceback/系统提示泄漏；OpenAPI 零变更 |
| AC-8 | 不破坏既有 Feature 与同模块行为 | 运行时/回归 | 回归 F4.1 / F4.2 / F4.4 + schedule delete / cancel rollback / scheduler 租户隔离 | 全部通过（回归 61 + F4.5 9 = **70**，详见 runtime-test-report.md） |

## 关键判定说明

### AC-1 为何必须 SERIALIZABLE（而不能只靠 `FOR UPDATE`）

- 目标时间段原本**无排期行**时，`SELECT ... WHERE <时间谓词> FOR UPDATE SKIP LOCKED` 锁的是空集，READ COMMITTED 下两个事务都判定"无冲突"后各自插入 → 双写。
- 仅当事务为 SERIALIZABLE 时，PostgreSQL SSI 基于**谓词锁**检测"两事务都读空集、又都向该谓词范围插入"的危险结构，在后者提交时抛 `40001`。
- AC-6(b) 的对照组用实证区分了保护来源：同一套 `FOR UPDATE SKIP LOCKED` 逻辑，RC 下双写 2 行、SERIALIZABLE 下 1 行 + 1 个 40001。

### AC-3/AC-4 注入方式的可信度

- 测试 monkeypatch `ScheduleRepository.find_conflicts` 抛出真实的 `asyncpg.exceptions.SerializationError("could not serialize access ...")`，与生产中 SSI 中止经 SQLAlchemy 包装后被 `_is_serialization_failure` 识别的异常同族（驱动 `sqlstate=="40001"` 或文案含 `could not serialize access`）。
- 生产中真实 40001 多在 `commit` 时抛出；识别函数对查询期与提交期两种来源都生效（统一在 `except Exception` 中判定）。

### AC-6 实证脚本（一次性诊断，已执行并清理，结论留痕于此）

- `SHOW transaction_isolation`：在 `rollback()` + `connection(execution_options={"isolation_level":"SERIALIZABLE"})` 之后，全新 session 与"先跑一条只读 SELECT 模拟 RBAC 上游事务"两路径均报 `serializable`，且 PostgreSQL 无 `there is already a transaction in progress` 告警。
- 因果对照（固定连接 + Barrier 严格同步）：`SERIALIZABLE` × {纯 SELECT, FOR UPDATE, FOR UPDATE SKIP LOCKED} 三组均 `['COMMITTED','40001_ABORT']`、落 1 行；`READ COMMITTED` + 纯 SELECT 组两次 `COMMITTED`、落 2 行。
- 适用边界：上述实验的前提是"两事务都从空谓词结果集出发"；`SKIP LOCKED` 在该前提下没有行可跳过，故三种 SELECT 写法表现一致。它不能证明 `SKIP LOCKED` 在"已存在且被第三方持锁的冲突行"场景下安全——该场景由 AC-5b / 实证 D 覆盖，并据此把最终实现定为普通快照读。

### AC-5b 持锁冲突行为何不会被 SSI 兜底（评审 NEEDS_FIX 要点）

- SSI 只跟踪**参与事务的快照/谓词依赖**：持锁方 X 是 READ COMMITTED 事务（预约/取消），不获取 SIREAD 锁，因此不会在 SSI 危险结构（rw-依赖环/pivot）中形成入边。
- 创建方 C 的 `FOR UPDATE SKIP LOCKED` 把可见但被锁的 S 跳过 → C 的读集合里既没有 S 这一事实行，也没有针对该行的谓词依赖 → C 提交时 SSI 无据可判，不产生 40001。
- 普通快照读不受行锁影响（行锁只阻塞"写/加锁读"，不阻塞快照读）：S 早已提交，对 C 的 SERIALIZABLE 快照必然可见 → 确定性 400。
- 回归用例在同一持锁窗口内同时断言 `use_lock=True → 空集` 与 `use_lock=False → 见 S`，把"漏判根因"和"修复有效性"固化在同一个测试里；并曾将调用点临时改回 `use_lock=True` 复现 `DID NOT RAISE`，确认用例具备缺陷检出力。

## HTTP 状态码与信封约定（对照 contracts.md）

- 端点 / 请求体 / 响应模型不变，无需 `pnpm gen:types`。
- 冲突：HTTP 400 + 信封 `code=400`、`msg` 为可展示的冲突描述。
- 并发耗尽：HTTP 500 + 信封 `code=500`、`msg` 为友好提示；不回显 SQL / traceback。
