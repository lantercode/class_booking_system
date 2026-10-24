# F4.5 — Release Note

## 排期创建并发安全（2026-10-02）

### 功能变更

- `POST /api/v1/schedules`（`ScheduleService.create_schedule`）的"冲突检查 → 插入"改为在同一 **SERIALIZABLE** 事务内完成：
  - 事务经 SQLAlchemy 官方入口 `AsyncSession.connection(execution_options={"isolation_level": "SERIALIZABLE"})` 提升（替代此前遗留的裸 `BEGIN ISOLATION LEVEL ...` 文本语句，消除 PostgreSQL `there is already a transaction in progress` 告警）；
  - 冲突检查使用**普通快照谓词读**（`find_conflicts(use_lock=False)`），不再带 `FOR UPDATE SKIP LOCKED`；
  - 捕获 SQLSTATE `40001`（SerializationFailure）自动以新快照重试，最多 3 次；确定性时间冲突直接返回 400 不重试；重试耗尽/其他异常返回友好 500 文案，不透传 traceback/SQL。
- 用户可感知行为：并发提交重叠排期时，以前可能偶现两条互相冲突的排期；现在稳定为"一个成功 + 另一个收到明确冲突提示（400）"，极端并发下表现为"稍后重试"提示（500），不会产生重叠脏数据。

### 修复

- **修复 1（空集双插）**：两个并发请求在目标时间段均无既有排期时，READ COMMITTED 下两边冲突检查都读空集后各自插入，产生两条重叠 NORMAL 排期。现由 SERIALIZABLE + SSI 谓词锁在提交期中止其一（40001）并重试/转为业务错误。
- **修复 2（评审发现，持锁冲突行被吞）**：当冲突排期已存在、且正被预约/取消事务（`increment_booked_count` / `decrement_booked_count` 持 schedule 行锁，READ COMMITTED）锁定时，旧检查的 `FOR UPDATE SKIP LOCKED` 会跳过该真实冲突行，且 SSI 对 RC 持锁方不建依赖、40001 不会触发，导致静默插入重叠排期。改为快照谓词读后，已提交冲突行不受行锁影响、必然可见，创建被确定性 400 拒绝。
  - 回归用例 `TestLockedConflictRowNotSkipped` 同时固化漏判根因（`use_lock=True` 探测为空集）与修复有效性（`use_lock=False` 见 S → 400）；修复前该用例实测 `DID NOT RAISE`。

### 兼容性

- API 路径、方法、请求体、响应模型、状态码语义（冲突 400 / 服务端友好错误 500）全部不变 → 无需 `pnpm gen:types`。
- 前端 4 端（admin-web / teacher-web / student-web / miniapp）零改动：成功响应不变；400/500 均沿用统一信封 `code/msg`，现有 toast 逻辑直接展示。
- 无 DB schema 变更、**无 migration**、无新依赖、无 Redis key 变更、无 MCP/AI 影响面；alembic head 保持 `f44ab1c2d3e4`。
- SERIALIZABLE 仅作用于单次创建事务；连接归还连接池时隔离级别由 SQLAlchemy 自动复位为 READ COMMITTED，不影响后续请求。
- `find_conflicts` 方法逻辑未变（仅修正 docstring），其余调用方（批量/更新路径）行为不变——其并发缺口见"已知遗留 / 技术债"。

### 运维与数据

- 无数据变更、无结构变更；仅应用层发布。
- 排期创建为低频管理写，SERIALIZABLE 重试窗口极小；建议监控日志关键字 `[ScheduleService] 创建排期遭遇 SerializationFailure`（warning）与重试耗尽 error，异常升高时排查排课并发来源。
- 冲突检查走既有索引 `idx_schedules_teacher_start` / `idx_schedules_classroom_start`，无新增慢查询；快照读不会被预约/取消的行锁阻塞。

### 部署步骤

```bash
# 1. 直接发布 apps/api（无 migration）
cd apps/api && PYTHONPATH=src .venv/bin/python -c "import app.main"  # 冒烟导入

# 2. 验证（应输出 alembic head 不变）
cd apps/api && PYTHONPATH=src .venv/bin/alembic heads
# 期望：f44ab1c2d3e4 (head)

# 3. 测试
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest \
  tests/integration/test_schedule_create_concurrency.py -v
# 期望：9 passed
```

回滚：回退应用版本即可；无库结构/数据需要回退。

### 已知遗留（LOW，不阻塞）

- 非 40001 异常（如外键 23503）当前统一转 500 且文案提示"并发冲突"，个别场景语义不够精确（旧路径部分为 409）；不产生脏数据，后续可按 sqlstate 细分。
- commit 成功后的 `refresh` 理论上可能"已成功却报失败"（窗口极小：refresh 已在连接池复位后的新 RC 事务执行）；保守保留，后续评估移除。
- 重试无 backoff/jitter；循环开头 `rollback()` 依赖"上游鉴权依赖无写操作"的约定（实测 RBAC checker 仅 SELECT，注释已标明）。
- 教室存在/可用校验在事务外，存在理论 TOCTOU（存量行为，教室维护状态变更极低频）。
- 测试缺口：并发用例均 `classroom_id=None`；暂无跨租户冲突、连接池隔离级别复位、SERIALIZABLE/RC 混跑专项用例。

### 技术债登记（见 backlog 附录）

- **D-F4.5-1（中）**：`batch_create_schedules`（`POST /schedules/batch`）仍为 READ COMMITTED + `use_lock=True`，存在与本 Feature 同构的两类并发缺口，需同方案加固。
- **D-F4.5-2（中低）**：`update_schedule` 仍为 READ COMMITTED + 快照读，时间字段更新存在 write skew 窗口，需评估同方案或排他约束。
- **D-F4.5-3（低，专项）**：以 DB 排他约束（`btree_gist` + tenant/teacher、tenant/classroom 两条部分排他约束）提供库内最终防重叠保证。
- **D-F4.5-4（低，清理）**：`find_conflicts` 手工 tenant 谓词与 ORM 自动注入叠加缺注释；排期 router 尾斜杠 `/schedules/` 不符 contracts.md 约定。

### 验证

- F4.5 集成测试 9/9；回归 F4.4(18) + F4.1(6) + F4.2(7) + schedule delete(9) + cancel rollback(12) + scheduler(9)，合计 **70/70 一次运行通过**；详见 [runtime-test-report.md](./runtime-test-report.md) 与 [review.md](./review.md)。
