# F6.3 静态验证报告（Static Verification）

> 日期：2026-10-22
> 方式：命令实跑 + 代码审查；所有结果可复现。
> 说明：本文件不替代运行时测试，运行时结论见 `runtime-test-report.md`。

## 1. 命令与结果

| # | 检查 | 命令 | 结果 |
|---|------|------|------|
| S1 | Python 语法 | `python3 -m py_compile`（21 个改动/新增文件） | PASS（`PY_COMPILE_OK`） |
| S2 | Lint | `ruff check`（本次相关文件） | 初次 12 errors（可自动修复）→ `--fix` 后 **All checks passed** |
| S3 | 迁移链 | `alembic heads` | 单一 head `a7b8c9d0e1f2` |
| S4 | 迁移往返 | `alembic upgrade head` → `downgrade -1` → `upgrade head` | PASS（本地 PG 15） |
| S5 | 迁移回填 | 本地 9 张 period 卡 | 回填后 0 NULL；二次执行影响 0 行 |
| S6 | 无 `ScheduleStatus.COMPLETED` | `rg -n "ScheduleStatus\.COMPLETED" apps/api/src` | 无输出 |
| S7 | Scheduler 不直写业务状态 | `rg -n "update\(Booking\)\|schedule\.status\s*=\s*ScheduleStatus" schedule/scheduler.py` | 无输出 |
| S8 | 期卡不走扣次 | 审查 `booking/service.py:164-179` | `deduct_credit` 仅在 `card_validation["deduct"]`（count）分支调用 |
| S9 | 期卡不回补 | 审查 `membership/service.py` `restore_credit` | period/unlimited 锁后 no-op；调用方（booking 取消、schedule 取消）无需改动 |
| S10 | 无越界改动 | 按 2026-10-22 10:40 后的文件 mtime 清单 | 仅 F6.3 允许范围（见第 3 节） |

## 2. 验收标准（A 组）对照

| AC | 结果 | 证据 |
|----|------|------|
| A-1 应用可导入 | PASS | 测试进程可正常收集并执行 41 条用例（隐含导入成功） |
| A-2 语法合法 | PASS | S1 |
| A-3 无 ScheduleStatus.COMPLETED | PASS | S6 |
| A-4 Scheduler 不直写 | PASS | S7 |
| A-5 期卡不走扣次 | PASS | S8 |
| A-6 期卡不回补 | PASS | S9 |
| A-7 API 契约无破坏性变更 | **代码审查 PASS / OpenAPI diff NOT RUN** | 未新增/删除端点；`booking/schemas.py`、`membership/schemas.py` 未改对外字段。未执行前后 OpenAPI 导出 diff |
| A-8 迁移可逆 | PASS | S3/S4 |
| A-9 回填可审计 | **部分 PASS** | 本地 0 NULL；生产回填清单 NOT RUN |
| A-10 无越界改动 | PASS | 第 3 节 |

## 3. 改动范围（mtime 证据）

```
apps/api/alembic/versions/a7b8c9d0e1f2_add_membership_card_validity_days.py
apps/api/src/app/core/config.py
apps/api/src/app/main.py
apps/api/src/app/modules/{booking,membership,schedule}/*
apps/api/tests/{membership_support.py,unit/test_membership_card_state_machine.py,integration/test_*.py}
docs/features/F6.3-membership-card-state-machine/*
docs/engineering/task-records/*
```

`.trae/**`、`.github/**`、`docs/features/F6.0-*`、`docs/delivery/**` 无今日修改（mtime 检查为空）。

## 4. 分层与安全审查

- Router 未新增业务判断；逻辑位于 Service。
- 跨模块仅调用 Service（`scheduler/scheduler.py` → `BookingService`；`booking/service.py` → `membership_card_service`）。
- Repository 继承 `TenantAwareRepository`，未发现裸 SQL（迁移回填 SQL 属于数据迁移，非运行时查询）。
- 未修改 RBAC 装饰器、租户中间件、JWT 链。

## 5. 未执行（NOT RUN / UNKNOWN）

| 项 | 原因 |
|----|------|
| `mypy` | CI 中为非阻塞步骤，本次未执行 |
| OpenAPI 前后 diff | 未导出快照；按"无端点/字段变更"人工核对 |
| 生产库回填统计 | 无生产库访问权限 |
| 全量 ruff（整仓） | 仅检查本次相关文件，避免历史未提交文件噪声 |
