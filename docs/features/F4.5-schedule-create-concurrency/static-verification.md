# F4.5 — 静态验证报告

> 日期：2026-10-02（评审回修后同步更新）
> 方法：minimal-change-guard —— 先冻结预期改动白名单，再以 `git status` / `git diff` 核对实际落点，actual ⊆ expected。

## 1. py_compile

```bash
python3 -m py_compile \
  apps/api/src/app/modules/schedule/service.py \
  apps/api/src/app/modules/schedule/repository.py \
  apps/api/tests/integration/test_schedule_create_concurrency.py
# 实际输出：COMPILE_OK（评审回修后逐次验证）
```

> IDE 对 sqlalchemy/pytest/app.* 的导入红线为 linter 未识别 venv 的误报；venv 下 py_compile 通过。

## 2. 预期改动白名单 vs 实际落点

| 预期文件（F4.5） | git 状态 | 实际内容 | 结论 |
|------------------|----------|----------|------|
| `apps/api/src/app/modules/schedule/service.py` | M | `create_schedule` 事务化 + SERIALIZABLE + 重试；新增常量/辅助函数；移除未用 `text` import；**评审回修：冲突检查 `use_lock=True → False`（+机理注释）** | 在白名单内 |
| `apps/api/src/app/modules/schedule/repository.py` | M（同文件混有预存改动） | **F4.5 hunk 仅 `find_conflicts` docstring**（方法逻辑零改动）；另含与本 Feature 无关的 `increment_booked_count` hunk，见 §3 | docstring hunk 在白名单内；skip_locked hunk 排除 |
| `apps/api/tests/integration/test_schedule_create_concurrency.py` | ??（新增） | **9 用例**并发集成测试（含评审回归 `TestLockedConflictRowNotSkipped`） | 在白名单内 |

显式核对（actual ⊆ expected）：

```bash
git status --short -- \
  apps/api/src/app/modules/schedule/service.py \
  apps/api/tests/integration/test_schedule_create_concurrency.py \
  apps/api/src/app/modules/schedule/repository.py
#  M apps/api/src/app/modules/schedule/repository.py      ← F4.5 docstring hunk + 预存 skip_locked hunk（见 §3）
#  M apps/api/src/app/modules/schedule/service.py         ← F4.5
#  ?? apps/api/tests/integration/test_schedule_create_concurrency.py  ← F4.5
```

## 3. 预存无关改动隔离（不回滚 / 不纳入）

工作区存在大量历史未提交改动（与本 Feature 无关）。`repository.py` 当前有**两个 hunk**：

```bash
git diff -- apps/api/src/app/modules/schedule/repository.py
# hunk A（F4.5）：find_conflicts docstring —— SKIP LOCKED 风险警告
# hunk B（预存）：increment_booked_count .with_for_update() → .with_for_update(skip_locked=True)（+注释）
```

- hunk B 属**预约抢名额并发**，与"排期创建并发安全"无关，**不回滚、不计入 F4.5 改动面**。
- `find_conflicts` 的**方法逻辑**（查询/谓词/两个 use_lock 分支）相对 HEAD 零改动；F4.5 仅改注释文字。
- 提交处置：`git add -p` 按 hunk 暂存，stage 范围 =
  - `apps/api/src/app/modules/schedule/service.py`（整文件仅 F4.5 改动）
  - `apps/api/src/app/modules/schedule/repository.py` 中**仅 docstring hunk**
  - `apps/api/tests/integration/test_schedule_create_concurrency.py`

## 4. 分层 / 架构规则清单（.trae/rules）

| 规则 | 检查 | 结果 |
|------|------|------|
| 分层 `Router → Service → Repository → DB` | Router 未改；事务边界在 `ScheduleService.create_schedule`；冲突查询仍走 `self.repo.find_conflicts`，未在 Service 拼裸 SQL 查 ORM | 通过 |
| Service 持事务边界 | 冲突检查 + `repo.create(auto_commit=False)` + `commit` 同一事务；隔离级别在 Service 设置 | 通过 |
| 跨模块复用走 Service | 仅复用同模块 Repository；教室校验走 `ClassroomRepository().get_by_id`（既有） | 通过 |
| 无裸 SQL 业务读写 | 全文件已无 `text(` 调用（grep 仅余注释文字）；移除裸 `BEGIN` 后 `from sqlalchemy import select` 不再 import `text` | 通过 |
| MCP/AI 不直连 Repository/DB | 本 Feature 不涉及 MCP；无 AI 写路径改动 | 通过（不涉及） |
| 租户隔离 | 不改三层机制；`find_conflicts` 内仍以 `get_tenant_id()`（ContextVar）追加 `tenant_id`，不接受请求体 tenant_id | 通过 |
| 认证 / RBAC | 端点 `get_current_user` + `@require_permissions("schedule:create")` 未动；循环内 `rollback()` 仅用于以干净连接重开 SERIALIZABLE，不改变鉴权结果 | 通过 |
| 事务隔离 / 幂等 | 40001 重试基于新快照重跑"检查+插入"，SSI 保证不双写；确定性 400 不重试；写操作不落部分状态；**冲突检查为快照谓词读（use_lock=False），无 SKIP LOCKED 吞持锁冲突行风险（AC-5b/实证 D）** | 通过（含 AC-6/AC-5b 实证） |
| 异常不透传 | 冲突 400 / 耗尽 500 均为 `BusinessException` 友好文案；不回显 SQL/堆栈/主机名；驱动异常仅记日志 | 通过 |
| 契约唯一事实源 | 无端点/请求体/响应模型变更 → OpenAPI 不变、无需 `pnpm gen:types` | 通过 |
| migration 链 | 无 schema 变更 → 无 migration；head 保持 `f44ab1c2d3e4` | 通过（不涉及） |

## 5. 事务实现要点静态核查

| 点 | 位置 | 结论 |
|----|------|------|
| 隔离级别用官方入口 | [service.py:130-132](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L130-L132) `db.connection(execution_options={"isolation_level":"SERIALIZABLE"})` | 非裸 BEGIN；无 PG WARNING（实证 C） |
| 设置前关闭上游事务 | [service.py:125-128](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py# L125-L128) `await db.rollback()`（容错 try/except） | 避免"已 autobegin 不可改隔离级别" |
| 检查与插入同事务 | [service.py:134-172](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L134-L172) | find_conflicts(`use_lock=False`) → create(auto_commit=False) → commit |
| 冲突检查禁用 SKIP LOCKED（评审回修） | [service.py:134-149](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L134-L149) 传 `use_lock=False` + 注释；[repository.py:114-131](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/repository.py#L114-L131) docstring 警告 | 快照读可见被 RC 持锁的已提交冲突行；SSI 兜底空集双插；第 9 用例固化 |
| 冲突不重试 | [service.py:174-175](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L174-L175) `except BusinessException: raise` | 确定性冲突立即返回 |
| 仅 40001 重试 + 上限 | [service.py:181-191](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L181-L191) | `attempt < 3` 才 continue；否则 500 |
| 消息在 rollback 前拼装 | [service.py:149-167](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L149-L167) | 避免 ORM 过期 greenlet_spawn |
| 纯校验在重试外 | [service.py:68-89](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/service.py#L68-L89) | 不占重试预算、无多余事务 |

## 6. 测试代码静态核查

- 无 mock DB / 无第二套驱动连接：统一用 `create_async_engine(get_settings().DATABASE_URL)`（单一连接来源，符合经验库约束），真实 asyncpg + 真实 PostgreSQL。
- 并发用两个独立 `AsyncSession`（不同连接）+ `asyncio.gather(..., return_exceptions=True)`，成功/失败分别断言。
- 身份经 `set_tenant_id(...)` 注入 ContextVar，与生产可信链路一致；不在数据体传 tenant_id。
- 每用例 `finally _cleanup` 删除 `capacity=78` 测试行；session fixture 结束兜底清理。
- AC-3/AC-4 monkeypatch 的是 `ScheduleRepository.find_conflicts`（真实 asyncpg 异常类型），非改 Service 私有状态。
- 第 9 例（AC-5b）不 mock：RC 锁方会话真实 `with_for_update()` 持锁不提交，probe 会话分别走 `use_lock=True/False` 两个真实查询分支，再走真实 Service 路径；锁在 `async with` 退出时回滚释放，finally 清理，无残留。

## 7. 契约 / 前端影响

- OpenAPI：无路径 / 方法 / 请求体 / 响应模型变化 → `packages/api-types` 无需重新生成。
- 4 端（admin / student / teacher / miniapp）：零改动；冲突 400 与并发耗尽 500 均沿用统一信封，前端现有错误处理可直接展示 `msg`。

## 8. 静态结论

- 实际代码改动 ⊂ 预期白名单（service.py 创建路径 + repository.py docstring hunk + 新增测试 9 例）；预存 skip_locked hunk 已隔离标注，提交时按 hunk 区分。
- 分层 / 租户 / 事务 / 异常 / 契约各项静态规则 **PASS**；评审 NEEDS_FIX 项（SKIP LOCKED 吞持锁冲突行）已在代码注释、Repository docstring 与回归用例三处闭环。
- 运行时类 AC（并发正确性 / SERIALIZABLE 生效 / 持锁冲突行 / 回归）见 [runtime-test-report.md](./runtime-test-report.md)。
