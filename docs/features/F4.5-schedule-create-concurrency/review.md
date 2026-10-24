# F4.5 — Review

> 日期：2026-10-02
> 审查组织：主控（内置总控）依协作协议组织**双专家独立评审**（backend-engineer / database-engineer），双方互不可见初稿；主控负责 Reconciliation。
> 评审轮次：两轮——首轮（修复前）→ NEEDS_FIX 回修 → 复核（修复后）。

## Scope

- `apps/api/src/app/modules/schedule/service.py`：`create_schedule` 同事务化 + SERIALIZABLE（官方 `connection(execution_options=...))`）+ 40001 最多 3 次重试 + 友好兜底；冲突检查调用 `use_lock=False`（评审回修）。
- `apps/api/src/app/modules/schedule/repository.py`：**仅 `find_conflicts` docstring** 补 `SKIP LOCKED` 风险警告；方法逻辑/SQL 零改动。
- `apps/api/tests/integration/test_schedule_create_concurrency.py`：新增 9 用例（真实 asyncpg + 真实 PostgreSQL）。
- Router / schemas / models / migration / OpenAPI / 前端 4 端 / MCP / Redis 均未改动；无新依赖；alembic head 保持 `f44ab1c2d3e4`。

## 首轮评审结论（修复前）

| 审查方 | 结论 | 核心意见 |
|--------|------|---------|
| backend-engineer | **READY_FOR_ACCEPTANCE** | 事务边界、重试分流、异常信封、契约零变更均合规；仅 5 个 LOW（见下"LOW 项登记"） |
| database-engineer | **NEEDS_FIX** | 创建路径 `find_conflicts(use_lock=True)` 存在静默双占漏判（见下 Conflict #1），窗口窄但正中 Feature 目标，修复成本极低 |

## Conflict Reconciliation（依 orchestration §8 记录）

### Conflict #1：`SKIP LOCKED` 是否会在 SERIALIZABLE 创建事务中漏判已存在冲突行

- **backend 立场**：早期实证 B 表明 SERIALIZABLE 下纯 SELECT / FOR UPDATE / SKIP LOCKED 三种写法在空集双插场景均为 1 行 + 1 个 40001；既有 8 测试全绿，故 READY。
- **database 立场（Evidence）**：
  1. `find_conflicts(use_lock=True)` 的实际 SQL 是 `FOR UPDATE SKIP LOCKED`——它**跳过当时无法立即加锁的行**，而非"锁住冲突行"；
  2. 预约/取消链路在整个事务期间持有 schedule 行锁（[repository.py `increment_booked_count`](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/repository.py) FOR UPDATE SKIP LOCKED、`decrement_booked_count` FOR UPDATE），且运行在 READ COMMITTED；
  3. 当冲突排期 S 已存在且正被上述 RC 事务持锁时，创建事务的冲突检查跳过 S → 空集 → 插入重叠行；
  4. RC 持锁方不获取 SIREAD 锁，SSI 危险结构（rw-依赖环/pivot）缺入边 → 创建方 commit 收不到 40001，重试机制完全不触发 → **静默双占**。
- **Impact**：违反 Feature 核心目标（并发不产生时间冲突排期）。触发需要"预约/取消事务进行中恰好并发创建重叠排期"，窗口窄，但排课与约课在同租户运营中真实共现；且一旦发生无日志、无错误、不可自愈。
- **主控核实**：评审意见与代码/PG 语义一致；早期实证 B 的 Barrier 实验只覆盖"双方从空集出发"，不覆盖"已存在行被第三方持锁"，不能反证该路径安全。
- **Recommendation（采纳 database 方案）**：
  1. service 创建调用点 `use_lock=True → False`（SERIALIZABLE 普通快照谓词读：已提交冲突行确定性可见 + SSI 兜底空集双插，PG 官方亦建议 SERIALIZABLE 下去掉多余 FOR UPDATE）；
  2. `find_conflicts` 逻辑不动（batch 等既有调用方语义保持），仅修正误导性 docstring；
  3. 新增真实会话回归用例，并对修复做因果翻转验证。
- **复核证据**：新增 `TestLockedConflictRowNotSkipped`——临时回退旧调用单跑该例实测 `FAILED: DID NOT RAISE`（漏判复现），修复后 PASS；F4.5 9/9、合计 70/70 全绿。
- **Reconciliation 结论**：Conflict #1 以 database-engineer 方案关闭；backend-engineer 的 LOW 项不阻塞，登记如下。

## Architecture

- 分层合规：Router 零改动；事务边界与隔离级别提升在 Service；冲突查询仍只经 Repository 方法（无裸 SQL、无跨层）；插入走 `repo.create(auto_commit=False)` 后由 Service 统一 commit。
- 同事务"快照谓词读 → 插入"是 SSI 成立前提；SERIALIZABLE 经 SQLAlchemy 官方入口设置，连接归还连接池时由 SQLAlchemy `reset_isolation_level` 复位为 READ COMMITTED（database-engineer 读源码确认，无跨请求污染）。
- 租户隔离：`find_conflicts` 继续以 ContextVar `get_tenant_id()` 追加租户谓词；身份不来自 LLM/请求体/LLM 无关路径，本 Feature 不改变三层隔离机制。

## Code

- 重试循环只包"rollback→提升隔离→冲突检查→插入→commit"临界区；纯校验在外，不耗重试预算。
- `BusinessException`（确定性 400）立即上抛不重试；仅 sqlstate `40001` / 文案 `could not serialize access` 重试，最多 3 次；耗尽/其他 → `BusinessException(500)`。
- 冲突消息在 rollback 前拼装（避免 ORM 过期后 greenlet_spawn）。
- Repository docstring 明确写出 `SKIP LOCKED` 的不完整性与"SERIALIZABLE 创建检查必须 False"，防止调用方未来误用。
- py_compile：service.py / repository.py / 测试文件均通过。

## Security

- 端点鉴权（`get_current_user` + `@require_permissions("schedule:create")`）未动；循环内 `rollback()` 仅用于以干净连接开启 SERIALIZABLE，不改变鉴权结果（RBAC checker 只做 SELECT，无上游写丢失风险）。
- 异常不透传：冲突 400 / 耗尽 500 均为统一信封友好文案，不回显 SQL / traceback / 主机名。
- OpenAPI 零变更，4 端与 MCP 无影响面。

## Transaction / Concurrency

- 两类并发危险均有闭环：
  1. **空集双插**（两并发创建）：SSI 谓词锁 → 一方 commit 收 40001 → 重试见冲突转 400，或耗尽友好 500（实证 B + AC-1/3/4）；
  2. **持锁已存在冲突行**（预约/取消 RC 事务持锁）：快照读不受行锁影响、S 必然可见 → 确定性 400（实证 D + AC-5b）。
- 不重叠并发不误伤：谓词范围不相交则无 rw-依赖（AC-2）。
- 无 schema 变更、无 migration、无新索引；谓词读复用 `idx_schedules_teacher_start` / `idx_schedules_classroom_start`。
- 幂等：冲突/失败路径均 rollback，无部分写入；重试从头重跑完整"检查+插入"。

## Regression

一次合并运行 **70 passed, 0 fail（5.86s）**：

- F4.5：9/9（含评审新增 AC-5b）。
- F4.4 `test_status_check_constraints.py`：18/18；F4.1 `test_booking_fk_membership_card.py`：6/6；F4.2 `test_order_fk_membership_card.py`：7/7。
- 同模块 `test_delete_schedule_service.py`：9/9；`test_cancel_schedule_rollback.py`：12/12；`test_scheduler_tenant_isolation.py`：9/9。

## Acceptance

- AC-1（重叠并发恰好一成一 400、1 行）：PASS（2 用例）。
- AC-2（不重叠并发均成功）：PASS。
- AC-3（一次性 40001 重试成功，2 次尝试）：PASS。
- AC-4（持续 40001 耗尽 → 友好错误、0 行）：PASS。
- AC-5（串行行为不回归）：PASS（3 用例）。
- **AC-5b（RC 持锁的已存在冲突行不被 SKIP LOCKED 吞掉）：PASS（修复前因果对照 DID NOT RAISE）**。
- AC-6（真实 SERIALIZABLE：SHOW/SSI/官方写法无 WARNING）：PASS（实证 A/B/C 留痕）。
- AC-7（分层/租户/异常合规）：PASS（static-verification.md）。
- AC-8（回归 70/70）：PASS。

## LOW 项登记（不阻塞，转 release-note 已知项/后续技术债）

| # | 项 | 评估 | 去向 |
|---|----|------|------|
| L1 | 非 40001 异常（如 FK 23503）统一转 500；旧路径部分场景为 409，文案"并发冲突"略误导 | 触发需异常数据（如教室被删），概率低；不产生脏数据 | release-note 已知项；后续可按 sqlstate 细分文案 |
| L2 | commit 成功后 `refresh` 若抛异常可能"已成功却报 500" | execution option 仅当次检出连接有效；refresh 在连接池复位后的新 RC 事务中执行，窗口极小；两专家对是否移除 refresh 意见不一，保守保留 | release-note 已知项 |
| L3 | 重试无 backoff/jitter；循环开头 `rollback()` 依赖"上游依赖无写"隐式约定 | 低频管理写；实测 RBAC checker 仅 SELECT；约定已写入代码注释 | release-note 已知项 |
| L4 | 教室存在/可用校验在事务外，存在 TOCTOU | 存量行为（改造前亦然）；教室维护状态变更极低频 | release-note 已知项 |
| L5 | 测试缺口：全部用例 `classroom_id=None`；无跨租户冲突、连接池 checkin 隔离级别复位、SERIALIZABLE 与 RC 混跑用例 | 核心路径已覆盖；建议后续补齐 | release-note 已知项 |
| L6 | 历史债务：`find_conflicts` 手工 tenant 谓词与 ORM 自动注入叠加但无注释；router `/schedules/` 尾斜杠不符 contracts.md | 与本 Feature 无关，不顺手扩 | 另立清理项 |
| L7 | `batch_create_schedules`（RC + use_lock=True，POST /schedules/batch 存活，风险中）与 `update_schedule`（RC + use_lock=False，write skew，风险中低）存在同构并发缺口 | backlog Scope 仅单个创建；**禁止在本 Feature 扩范围** | **转 backlog 技术债 D-F4.5-1 / D-F4.5-2** |
| L8 | 库内最终保证可上 EXCLUDE 约束（需 btree_gist + tenant/teacher、tenant/classroom 两条部分排他约束） | 更强但改动面大，需专项评估 | 技术债 D-F4.5-3（承接 U3） |

## 结论

首轮 NEEDS_FIX 项已按 database-engineer 方案修复并经因果翻转与 70/70 回归复核；双专家分歧已按 Reconciliation 流程关闭。剩余均为 LOW / 既有项，已登记去向。

**READY_FOR_ACCEPTANCE**
