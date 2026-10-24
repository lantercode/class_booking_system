# F4.5 — 排期创建并发安全 · 实施方案

> Feature ID：F4.5
> 作者：主控（内置总控）联合 backend / database 双域规则清单核对
> 日期：2026-10-02
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)
> 形态说明：本 Feature 代码主体为前序会话遗留、测试已绿但缺产物与关键正确性实证；本次按交付流水线**先实证、再修正事务开启方式、补齐 9 产物**，不推倒重写。
> **评审修订（2026-10-02）**：双专家独立评审中 database-engineer 判定 NEEDS_FIX——`use_lock=True` 的 `SKIP LOCKED` 会吞掉"已存在且正被并发 RC 事务持行锁的真实冲突行"，SSI 无法兜底。主控经因果复现后采纳，创建路径改为 `use_lock=False`（详见实证 D 与 D2′，流程回阶段 7 修正后重新出评审）。

---

## Root Cause

并发创建同一教师/教室重叠排期可能双写，根因是"检查→插入"在默认 READ COMMITTED 下不具备快照可串行性：

1. 两事务的冲突检查 `SELECT ... WHERE <时间重叠谓词> FOR UPDATE SKIP LOCKED` 在目标时间段**无既有行**时都读到空集；
2. 空结果集上没有行可锁，`FOR UPDATE SKIP LOCKED` 等价于无锁；
3. READ COMMITTED 每条语句拿新快照，两个事务各自看到"无冲突"，都执行 INSERT → 两条重叠排期。

仅靠行锁无法堵住"空集双插"；需要 SERIALIZABLE 的 SSI 谓词锁在提交期制造 rw-依赖并中止其一（40001），再由 Service 有限重试把冲突转成确定性的业务 400。

## 已核查的代码与 DB 事实（Evidence）

| 事实 | 证据 |
|------|------|
| 改造前 `create_schedule` 无 SERIALIZABLE / 无重试 | `git show HEAD:apps/api/src/app/modules/schedule/service.py`：`find_conflicts(use_lock=True)` 后直接 raise 或 `create` |
| `find_conflicts(use_lock=...)` 与 `.with_for_update(skip_locked=True)` 为**既有** | [repository.py:103-181](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/repository.py#L103-L181)；本 Feature **仅修正其 docstring（逻辑零改动）**，评审后将创建路径调用改为 `use_lock=False` |
| 时间重叠谓词 + 租户 + 仅 NORMAL | [repository.py:129-161](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/repository.py#L129-L161) |
| SSI 实证：RC 双写 / SER 拦截 | 因果对照实验（见下"关键实证"） |
| 隔离级别设置入口在当前 SA 版本可用 | `AsyncSession.connection(execution_options={"isolation_level": ...})` 实测：两路径 SHOW=serializable、无 PG WARNING、重试可重复提升 |
| 无 schema 变更；head=`f44ab1c2d3e4` | 不改表/约束/索引 → 无 migration |

### 关键实证（本 Feature 主控把关，一次性脚本已执行并清理，结论留痕）

**实证 A：隔离级别是否真实生效（破除"裸 BEGIN 静默失效"疑虑）**

- 前序遗留实现用 `await db.execute(text("BEGIN ISOLATION LEVEL SERIALIZABLE"))`。
- 实测：SQLAlchemy asyncpg 适配器在执行该语句前会先用 asyncpg 原生事务发一条裸 `BEGIN`（RC），随后文本语句到达 PostgreSQL；PostgreSQL 对"事务内重复 `BEGIN ... ISOLATION LEVEL`"给 `WARNING: there is already a transaction in progress`，**但 ISOLATION LEVEL 子句会被应用**（实测可在事务内升/降隔离级别，SHOW 随之变化）。故功能上确实进入 serializable，但依赖非显然边界行为且每请求产生一条 WARNING。
- 进一步以 wire 抓包确认，并发现适配器会丢弃/重建内部事务对象（脆弱信号）。

**实证 B：保护来源因果对照（`asyncio.Barrier(2)` 强制两事务都完成快照读后才插入）**

| 组（同一套 SELECT FOR UPDATE SKIP LOCKED + INSERT 逻辑，唯一变量=隔离级别） | 结果 | 落库 |
|------|------|------|
| SERIALIZABLE + 纯 SELECT | 1 COMMITTED + 1 `40001_ABORT` | 1 |
| SERIALIZABLE + FOR UPDATE | 1 COMMITTED + 1 `40001_ABORT` | 1 |
| SERIALIZABLE + **FOR UPDATE SKIP LOCKED**（现有用法） | 1 COMMITTED + 1 `40001_ABORT` | **1** |
| READ COMMITTED + 纯 SELECT（对照） | 2 COMMITTED | **2（漏洞复现）** |

→ 证明（适用范围需注意）：`FOR UPDATE SKIP LOCKED` 用法在"**双方都从空谓词结果集出发**的并发插入"场景下，SERIALIZABLE 确由 SSI 谓词锁兜底；这也解释了并发集成测试为何通过。但该实验**未覆盖"已存在冲突行正被第三方事务持锁"**场景——见实证 D，正是评审发现的漏判。

**实证 C：官方写法替代**

- `rollback()` 后 `await db.connection(execution_options={"isolation_level":"SERIALIZABLE"})`：全新 session 与"有上游只读事务"两路径均 SHOW=`serializable`、`notices=[]`（无 WARNING）；模拟重试（rollback 后再次提升）仍 SHOW=`serializable`。
- BEGIN 由 asyncpg 原生事务 API 发出（不经过裸 cursor 语句），为 SQLAlchemy 官方文档支持路径。

> 诊断过程中曾因把连接池当连接使用（`pool.execute` 不跨语句保持事务）得到一次"SER 也双写"的假象，已定位为实验脚本 bug（日志出现 `Resetting connection with an active transaction`），改为"worker 内固定持有同一连接"后结论以上表为准。

**实证 D：评审 NEEDS_FIX——被并发 RC 事务持锁的"已存在冲突行"被 SKIP LOCKED 吞掉（因果复现）**

- 背景：预约/取消链路的 `increment_booked_count`（FOR UPDATE SKIP LOCKED）/ `decrement_booked_count`（FOR UPDATE）在整个事务期间持有 `course_schedules` 行锁；该锁方运行在 READ COMMITTED，不产生 SIREAD 锁。
- 构造：① 已提交的 NORMAL 排期 S；② 另一个 RC 事务对 S 执行 `SELECT ... FOR UPDATE` 不提交；③ 此刻以 SERIALIZABLE 创建与 S 重叠的排期。
- 结果（新增集成测试 `TestLockedConflictRowNotSkipped`，并对修复做了因果对照）：
  - `find_conflicts(use_lock=True)`：`FOR UPDATE SKIP LOCKED` **跳过被持锁的 S → 返回空集**（测试断言固化该根因）；旧 Service 路径因此 `DID NOT RAISE`，重叠行静默落库——锁方为 RC，SSI 依赖图缺入边，commit 期**收不到 40001**。
  - `find_conflicts(use_lock=False)`：SERIALIZABLE 普通快照谓词读仍可见已提交的 S → 返回冲突；修复后 Service 路径抛 `BusinessException(400)`，窗口内始终 1 行。
- 结论：创建事务中 `SKIP LOCKED` 不仅无必要（SSI 已覆盖空集双插），而且有害（吞掉真实冲突）。PG 官方亦建议 SERIALIZABLE 下去掉多余的 `FOR UPDATE`。修复 = 调用点改 `use_lock=False` + Repository docstring 补警告，方法逻辑不动。

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/modules/schedule/service.py` | 修改 `create_schedule`：事务化 + SERIALIZABLE + 40001 重试 + 友好兜底；新增模块常量 `_CREATE_SERIALIZABLE_MAX_ATTEMPTS=3` 与 `_is_serialization_failure`；移除不再使用的 `text` import；**评审修订：冲突检查调用由 `use_lock=True` 改为 `use_lock=False` 并注释原因** |
| 2 | `apps/api/src/app/modules/schedule/repository.py` | **仅修正 `find_conflicts` docstring**：明确 `SKIP LOCKED` 会跳过被持锁冲突行、SERIALIZABLE 创建检查必须传 `use_lock=False`；方法逻辑零改动（该文件中 `increment_booked_count` 的 skip_locked 是工作区预存无关改动，见 U4，不回滚不纳入） |
| 3 | `apps/api/tests/integration/test_schedule_create_concurrency.py` | 新增集成测试（**9 用例**：原 8 用例覆盖 AC-1~AC-5；第 9 个 `TestLockedConflictRowNotSkipped` 为评审 NEEDS_FIX 的回归固化；AC-6 由实证脚本留痕） |

**明确不在本 Feature 改动范围**：`find_conflicts` 方法逻辑/Router / schemas / models / migration / OpenAPI / 前端 / MCP / Redis。

## Exact Fix（service.py）

```python
_CREATE_SERIALIZABLE_MAX_ATTEMPTS = 3

def _is_serialization_failure(exc):           # 识别 sqlstate == "40001" 或文案
    orig = getattr(exc, "orig", exc)
    return getattr(orig, "sqlstate", None) == "40001" \
        or "could not serialize access" in str(orig)

# create_schedule：
# 1) 纯校验全部放在 for 循环之外
# 2) 尝试循环（1..3）：
for attempt in range(1, _CREATE_SERIALIZABLE_MAX_ATTEMPTS + 1):
    try:
        await db.rollback()                  # 关闭上游只读事务（容错）
        await db.connection(                # 官方入口提升隔离级别
            execution_options={"isolation_level": "SERIALIZABLE"})
        # SERIALIZABLE 下普通快照谓词读：SSI 谓词锁兜底空集双插；
        # 禁止 use_lock=True——SKIP LOCKED 会吞掉被并发 RC 事务持锁的真实冲突行（实证 D）
        conflicts = await self.repo.find_conflicts(..., use_lock=False)
        if conflicts["has_conflict"]:
            error_messages = [...]          # 必须在 rollback 前拼装
            await db.rollback()
            raise BusinessException("；".join(error_messages), code=400)
        schedule = await self.repo.create(db, schedule_data, auto_commit=False)
        await db.commit(); await db.refresh(schedule); break
    except BusinessException:
        raise                                # 确定性冲突不重试
    except Exception as exc:
        await db.rollback()
        if _is_serialization_failure(exc) and attempt < 3:
            continue                         # 40001 → 以新快照重试
        raise BusinessException("创建排期失败，请稍后重试…", code=500)
```

## 关键决策记录（Decision）

| # | 决策 | 理由 |
|---|------|------|
| D1 | **同时**采用 T4.5.1（同事务）与 T4.5.2（SERIALIZABLE），而非二选一 | backlog 写"或"，但实证 B 表明：仅"同事务 + FOR UPDATE"在 RC 空集场景仍双写；必须 SERIALIZABLE 的 SSI 谓词锁才能保证不重叠。"检查→插入"同事务是 SSI 成立的前提，SSI 谓词锁兜底"空集双插" |
| D2 | ~~保留既有 `find_conflicts(use_lock=True)`，不改 Repository~~ **（已被 D2′ 取代，留痕）** | 原理由"已存在冲突行走行锁快速确定性 400"忽略了 `SKIP LOCKED` 对**被持锁行**的跳过语义；实证 D 证明该路径存在静默双占，且 40001 无法兜底 |
| D2′ | **评审修订：创建路径改 `find_conflicts(use_lock=False)`；Repository 只改 docstring 不改逻辑** | ① SERIALIZABLE 普通快照谓词读对"已提交的已存在冲突行"本就直接可见 → 确定性 400，不依赖行锁；② 空集双插由 SSI 谓词锁兜底；③ `SKIP LOCKED` 会吞掉正被并发 RC 事务（预约/取消）持锁的真实冲突行，而 RC 锁方无 SIREAD 锁，SSI 图缺边 → 40001 不触发（实证 D 因果复现：旧代码 `DID NOT RAISE`）；④ PG 官方建议 SERIALIZABLE 下去掉多余 FOR UPDATE。新增第 9 个集成测试固化正反两面 |
| D3 | 用官方 `connection(execution_options=...)` 替换遗留的裸 `text("BEGIN ...")` | 实证 A/C：裸写法功能正确但每请求产生 PG WARNING、依赖"事务内重复 BEGIN 仍应用 ISOLATION 子句"的边界行为并触发适配器事务对象重建；官方写法零 WARNING、行为受文档保证、重试安全。改动仅 1 处、风险低（AC-1~AC-5 重测全绿） |
| D4 | 最大尝试 3 次；纯校验放重试外 | 排课为低频管理写，冲突窗口极小；无状态校验不占重试预算、不产生事务开销；重试只包住"读快照→写"这一可能 40001 的临界区 |
| D5 | `BusinessException(400)` 立即上抛、不重试；仅 40001 重试 | 确定性时间冲突重试结果不变；40001 是可安全重试的瞬态可序列化失败（PostgreSQL 官方推荐重试） |
| D6 | 冲突错误消息在 `rollback()` 前拼装 | rollback 使 ORM 实例过期，事后访问 `c.start_at` 会触发 asyncio 下 `greenlet_spawn` 错误 |
| D7 | 不引入排他约束（EXCLUDE USING gist） | 超出 backlog 指定的事务方案；需 `btree_gist` 扩展与 tenant+teacher/classroom+时间多维约束设计；当前 SERIALIZABLE 方案已满足目标，另立评估（U3） |
| D8 | 不改 `batch_create_schedules` | backlog Scope 仅单个创建；不顺手扩范围（U2） |
| D9 | 无 migration | 无 schema 变更；隔离级别是事务级运行时参数，不需要也不应固化到库结构 |

## Dependency Analysis

- 复用既有 `course_schedules` 表 + `idx_schedules_teacher_start` / `idx_schedules_classroom_start`（利于 SSI 谓词锁落在索引）。
- 复用既有 Repository / 异常体系 / 认证鉴权 / 租户上下文；无新依赖、无 OpenAPI/Redis/前端/MCP 影响。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 提升 SERIALIZABLE 增加 40001 概率 / 重试开销 | 低~中 | 仅单个创建事务、低频写；3 次重试；耗尽只友好失败不脏写；监控重试日志（U1） |
| 上游依赖已开事务导致无法更改隔离级别 | 中 | 循环内先 `rollback()` 关闭上游事务再 `connection(options)`；实证两路径可用、重试可重复提升 |
| 重试引发重复插入 | 低 | 每次尝试以新快照重新做冲突检查；插入与检查在同一 SERIALIZABLE 事务，SSI 保证不双写 |
| 影响同模块 delete/cancel/查询 | 低 | 仅改 `create_schedule`；回归 delete(9) / cancel rollback(12) / scheduler(9) 全绿 |
| 误伤不重叠并发 | 低 | AC-2 实证不重叠两者均成功（谓词范围不相交） |

## Implementation Steps

1. 实证隔离级别与 SSI 因果（实证 A/B/C，一次性脚本，结论入文档）。
2. 修正 service.py 事务开启为官方写法 + 移除 `text` import → `py_compile`。
3. 运行既有 8 个并发集成测试，确认全绿。
4. 静态核对改动面（预存无关改动单独标注）。
5. 回归 F4.1/F4.2/F4.4 + 同模块 delete/cancel/scheduler。
6. 双专家独立评审（backend / database）；database-engineer 判定 NEEDS_FIX（实证 D）。
7. **回阶段 7 修正**：service 调用点 `use_lock=True → False`、repository docstring 补警告、新增第 9 个持锁冲突回归用例；对旧代码做因果对照（`DID NOT RAISE`）后还原修复；`py_compile`。
8. 重跑 F4.5 全量（9/9）+ 回归套件（合计 70/70）。
9. 产出 9 份产物 + backlog 标记 DONE。

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1 | `TestConcurrentCreateConflict` 2 用例（完全/部分重叠） |
| AC-2 | `test_concurrent_non_overlapping_both_succeed` |
| AC-3 | `test_serialization_failure_retried_and_succeeds`（一次性注入） |
| AC-4 | `test_serialization_failure_exhausted_returns_business_error`（持续注入，断言尝试次数/文案/落库 0） |
| AC-5 | `TestSerialBehaviorUnchanged` 3 用例 |
| AC-5b | `TestLockedConflictRowNotSkipped`（评审回归：RC 持锁的已存在冲突行不被 SKIP LOCKED 吞掉 → 400；同用例内固化 use_lock=True 漏判根因） |
| AC-6 | 实证 A（SHOW）+ 实证 B（Barrier 因果对照）+ 实证 C（官方写法无 WARNING）+ 实证 D（持锁冲突行因果复现），结论留痕 acceptance.md |
| AC-7 | static-verification.md 逐条规则清单 |
| AC-8 | runtime-test-report.md 回归套件 |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 生产 40001 触发率 / 重试后失败率 | dev 不可压测；低频写 + 3 次重试足够；建议监控 warning 日志 |
| U2 | `batch_create_schedules` 仍 RC + 行锁 | 另立 Feature 评估，不本批扩范围 |
| U3 | 是否上排他约束 EXCLUDE GIST | 需 btree_gist 与多维约束设计，另立专项 |
| U4 | `increment_booked_count` skip_locked 预存改动 | 与本 Feature 无关；提交时只 stage service.py + 新测试 |
