# F4.5 — 排期创建并发安全 · 实施报告

> 日期：2026-10-02 ｜ 执行：主控（内置总控）联合 backend / database 双域规则清单核对
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

本 Feature 属于"遗留半成品收尾"：`create_schedule` 的 SERIALIZABLE + 重试主体逻辑与 8 个并发测试已由前序会话写好（测试全绿），但缺少 9 份交付产物，且事务开启方式存在一个未经实证的关键疑虑。本次按交付流水线完成：

1. **实证（核心把关）**：通过 SHOW / wire 抓包 / `asyncio.Barrier` 因果对照三组一次性诊断，证明 (a) 创建事务确实进入 SERIALIZABLE；(b) 保护来自 SSI（RC 对照双写、SER 拦截）；(c) 前序遗留的裸 `text("BEGIN ISOLATION LEVEL SERIALIZABLE")` 虽功能正确，但每请求产生一条 PostgreSQL `WARNING: there is already a transaction in progress` 并依赖非显然边界行为。
2. **一处最小修正**：将事务开启替换为 SQLAlchemy 官方入口 `db.connection(execution_options={"isolation_level": "SERIALIZABLE"})`，并移除随之不再使用的 `text` import；重试 / 冲突检查 / 错误拼装等逻辑保持不变。
3. **评审回修（阶段 7→9 回路）**：双专家独立评审，backend-engineer 判 READY_FOR_ACCEPTANCE（仅 5 个 LOW），**database-engineer 判 NEEDS_FIX**——`find_conflicts(use_lock=True)` 的 `SKIP LOCKED` 会吞掉被并发 RC 事务（预约/取消）持行锁的已存在冲突行，且 SSI 无法兜底。主控以新增集成测试 + 临时回退因果对照（旧代码 `DID NOT RAISE`）确认缺陷成立后采纳：调用点改 `use_lock=False`、Repository 仅补 docstring、新增第 9 个回归用例（D2′/实证 D）。
4. **验证**：修复后 F4.5 9/9 通过；与 F4.1/F4.2/F4.4 + schedule delete/cancel + scheduler 一次合并运行合计 **70/70 通过**。
5. 补齐 9 份产物并在 backlog 标记 DONE。

## 2. 变更明细

### 2.1 [apps/api/src/app/modules/schedule/service.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py)（修改）

| 位置 | 变更 |
|------|------|
| L11 | import 从 `sqlalchemy import select, text` 改为 `sqlalchemy import select`（裸 BEGIN 移除后 `text` 不再被使用） |
| L31-32 | 新增 `_CREATE_SERIALIZABLE_MAX_ATTEMPTS = 3` |
| L35-44 | 新增 `_is_serialization_failure(exc)`：识别 `orig.sqlstate == "40001"` 或文案含 `could not serialize access`（兼容 SQLAlchemy 包装与驱动原生异常） |
| L59-64 | `create_schedule` docstring 说明 F4.5 事务/重试语义 |
| L70-91 | 无状态纯校验（时间范围、预约开放/截止、取消截止、教室存在/可用）移到重试循环**之外** |
| L116-193 | 事务内"冲突检查 → 插入"重试循环：`rollback()` 关上游事务 → **L130-132 `db.connection(execution_options={"isolation_level":"SERIALIZABLE"})`（本次由裸 BEGIN 修正为官方写法）** → **`find_conflicts(use_lock=False)`（评审修订，L134-149 附 SKIP LOCKED 漏判机理注释）** → 冲突则在 rollback 前拼装消息后 `BusinessException(400)`；无冲突 `repo.create(auto_commit=False)` + `commit` + `refresh` |
| L167-184 | 异常分流：`BusinessException` 直接上抛；40001 且未耗尽 → `continue` 重试；耗尽/其他 → `BusinessException(500)` 友好文案 |
| L186-190 | 循环结束仍无 `schedule` 的兜底 500（防御性，正常不可达） |

### 2.2 [apps/api/src/app/modules/schedule/repository.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/repository.py)（修改，仅 docstring）

- `find_conflicts` docstring（约 L114-131）：把"创建排期时应设置为 True，确保事务隔离"的**误导性说明**替换为 `SKIP LOCKED` 语义警告——会跳过被持锁冲突行、不保证检测完整性；SERIALIZABLE 创建冲突检查必须传 `use_lock=False`。
- **方法逻辑 / SQL 零改动**（查询、谓词、`with_for_update(skip_locked=True)` 分支保持 HEAD 原样）。
- 同一文件中 `increment_booked_count` 的 `with_for_update(skip_locked=True)` 为工作区预存无关改动（U4），不属于本 Feature。

### 2.3 [apps/api/tests/integration/test_schedule_create_concurrency.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/tests/integration/test_schedule_create_concurrency.py)（新增，9 用例）

- `shared_data`（session）：解析种子 tenant / teacher（13800138001）/ 任一 course，返回纯数据 dict；结束兜底清理 `capacity=78` 测试排期。
- `sf`（function）：独立 engine（pool≥4 支撑双事务并发）+ session_factory。
- helper：`_create_via_service`（独立 session 调 Service，模拟一个并发请求）、`_count_window`、`_cleanup`。
- 数据隔离：`capacity=78` + 2099 时间窗；不依赖列默认值之外的字段（created/updated 有 server_default）。
- **评审新增 `TestLockedConflictRowNotSkipped`（第 9 用例）**：RC 会话持 S 行锁不提交 → 同窗口断言 `use_lock=True` 探测为空集（漏判根因固化）、`use_lock=False` 探测见 S → Service 创建抛 `BusinessException(400)`、窗口仅 1 行。

## 3. Scope Verification（最小改动核查）

- 本 Feature 业务代码改动为 `schedule/service.py`（创建路径）+ `schedule/repository.py`（**仅 docstring hunk**）；测试新增 1 个文件。
- `schedule/repository.py` 中 `find_conflicts` 的**方法逻辑**相对 HEAD 零改动（`use_lock` / `with_for_update(skip_locked=True)` 分支均为既有，已逐行核对）；本 Feature 只改其 docstring 与 service 侧调用实参。
- 工作区另有大量与本 Feature 无关的预存改动；其中 `schedule/repository.py` 的 `increment_booked_count` 由 `with_for_update()` 改为 `with_for_update(skip_locked=True)`（预约抢名额并发）与 F4.5 无关：**不回滚、不纳入本 Feature**（U4）。提交时须按 hunk stage：service.py + repository.py 的 docstring hunk + 新测试文件，跳过 skip_locked hunk。
- Router / schemas / models / migration / OpenAPI / 前端 / MCP / Redis 均未触碰。

## 4. Tests Run

修复后一次合并运行（`pytest <7 个文件>`）：

| 套件 | 用例数 | 结果 |
|------|--------|------|
| `test_schedule_create_concurrency.py`（F4.5 主测试，含评审新增第 9 例） | 9 | **9 passed**（0.50s） |
| `test_status_check_constraints.py`（F4.4 回归） | 18 | passed |
| `test_booking_fk_membership_card.py`（F4.1 回归） | 6 | passed |
| `test_order_fk_membership_card.py`（F4.2 回归） | 7 | passed |
| `test_delete_schedule_service.py`（同模块） | 9 | passed |
| `test_cancel_schedule_rollback.py`（同模块） | 12 | passed |
| `test_scheduler_tenant_isolation.py`（同模块） | 9 | passed |
| 合计 | 70 | **70 passed**（5.86s） |
| `py_compile service.py / repository.py / 测试文件` | — | OK |

因果对照（修复检出力验证）：临时把 service 调用点改回 `use_lock=True` 后单跑第 9 例 → **FAILED: DID NOT RAISE**（静默双占复现）；还原 `use_lock=False` 后 9/9 通过。

warnings 均为既有第三方 deprecation（passlib `crypt`、FastAPI `example`、unittest mock），与本 Feature 无关。

## 5. Results（与 AC 对照）

- AC-1（完全/部分重叠并发只一成功、另一个 400、DB 1 行）：PASS（2 用例）。
- AC-2（不重叠并发均成功、DB 2 行）：PASS。
- AC-3（一次性 40001 重试后成功，2 次尝试）：PASS。
- AC-4（持续 40001 三次耗尽 → 友好 BusinessException、文案含"重试"、0 行）：PASS。
- AC-5（串行冲突 400 / 合法创建 / 非法时间参数 ValidationException）：PASS（3 用例）。
- AC-5b（RC 持锁的已存在冲突行不被 SKIP LOCKED 吞掉 → 400、窗口 1 行；同例固化漏判根因）：PASS（第 9 用例；旧代码因果对照 DID NOT RAISE）。
- AC-6（真实 SERIALIZABLE：SHOW + SSI 因果实证 + 官方写法无 WARNING）：PASS（实证留痕 implementation-plan.md / acceptance.md）。
- AC-7（分层 / 租户 / 异常合规）：PASS（见 static-verification.md）。
- AC-8（回归）：PASS（70/70 一次合并运行）。

## 6. 实施中发现的问题与处置

| # | 问题 | 处置 |
|---|------|------|
| 1 | 裸 `text("BEGIN ISOLATION LEVEL SERIALIZABLE")` 是否真生效存在疑虑（可能双 BEGIN / 静默 RC） | 实证：功能上确实升到 serializable（PG 对事务内重复 BEGIN 应用 ISOLATION 子句），但产生 WARNING 且依赖边界行为 → 改用官方 `connection(execution_options=...)`（D3） |
| 2 | 首次因果实验误把连接池当连接，得到"SER 也双写"假象 | 定位为脚本 bug（`pool.execute` 不保持事务 + `Resetting connection with an active transaction` 日志），改为 worker 固定持有同一连接 + Barrier 同步后结论反转（SER 拦截） |
| 3 | 冲突消息若在 rollback 后访问 ORM 对象会 greenlet_spawn 报错 | 保持前序正确写法：rollback 前拼装消息（D6），并在代码注释标明 |
| 4 | 工作区预存无关改动（increment_booked_count skip_locked 等） | 不回滚不纳入，scope 透明记录（U4） |
| 5 | **评审 NEEDS_FIX**：`use_lock=True` 的 SKIP LOCKED 吞掉被并发 RC 事务（预约/取消）持锁的已存在冲突行，SSI 不兜底 → 静默双占 | database-engineer 发现、主控因果复现（新增第 9 例 + 临时回退 DID NOT RAISE）后采纳：调用点改 `use_lock=False`、Repository 补 docstring（D2′/实证 D）；70/70 复验 |

## 7. Risks

- 生产 SERIALIZABLE 重试率未知（U1）：低频管理写 + 3 次重试 + 友好兜底，不产生脏数据；建议监控。
- `batch_create_schedules` 未含同等保护（U2）：超出 Scope，另立 Feature。

## 8. UNKNOWN

同 [implementation-plan.md](./implementation-plan.md) UNKNOWN U1~U4，无新增未决项。

## 9. Handoff

- 后端视角（backend-engineer 关注点）：事务边界在 Service；40001 重试只包临界区、确定性 400 不重试；异常经统一信封不透传；Router/schemas/契约零改动。
- 数据库视角（database-engineer 关注点）：隔离级别经官方入口设置且有 SHOW/SSI 实证；冲突检查为 SERIALIZABLE 快照谓词读（无 SKIP LOCKED 吞行风险，持锁冲突行有回归用例）；无 schema 变更、无 migration、head 仍 `f44ab1c2d3e4`；谓词锁复用既有教师/教室时间索引；租户谓词保持。
- 前端：无改动、无需重新生成类型。
- REVIEW 结论：经一轮 NEEDS_FIX 回修后 READY_FOR_ACCEPTANCE（见 [review.md](./review.md)）。
