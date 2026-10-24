# F6.4 静态验证报告

> 日期：2026-10-22
> 方式：命令实跑 + 代码审查。

## 1. 命令与结果

| # | 检查 | 命令 | 结果 |
|---|------|------|------|
| S1 | 语法 | `python3 -m py_compile`（3 个改动/新增文件） | PASS（`PY_COMPILE_OK`） |
| S2 | Lint | `.venv/bin/ruff check`（同 3 文件） | **All checks passed**（首轮通过，无返工） |
| S3 | 无迁移变更 | 无新增 alembic 版本 | PASS |
| S4 | 无路由/DTO 变更 | `git diff` 仅 repository/service/测试 | PASS |
| S5 | 无越界改动 | 11:35 后 mtime 清单 | PASS（仅预期 8 个文件，其中 5 份为文档） |

```
apps/api/src/app/modules/booking/repository.py
apps/api/src/app/modules/booking/service.py
apps/api/tests/integration/test_booking_time_overlap.py
docs/features/F6.4-booking-time-overlap/{requirement,user-flow,acceptance,implementation-plan,implementation-report,static-verification,runtime-test-report,review,release-note}.md
docs/engineering/task-records/20261022-F6.4-booking-time-overlap.md
```

## 2. 验收标准（A 组）

| AC | 结果 | 证据 |
|----|------|------|
| A-1 应用可导入 | PASS | 测试进程正常收集并执行 8 条用例 |
| A-2 Lint | PASS | S2 |
| A-3 分层 | PASS | Router 未改；校验在 Service |
| A-4 租户 | PASS | Repository 继承 `TenantAwareRepository`；JOIN 查询显式叠加 `Booking.tenant_id` 并注释 |
| A-5 契约 | PASS | 无端点/字段变更 |
| A-6 与 D9 解耦 | PASS | 未改 `validate_card_for_booking` / `deduct_credit`；校验位于卡校验之后 |
| A-7 范围 | PASS | S5 |

## 3. 代码审查要点

- advisory lock 属于数据访问层的并发原语，不含业务判断；未引入"降级放行"分支。
- 未发现裸 SQL 业务查询（唯一 `text()` 为 `pg_advisory_xact_lock`，无数据读写）。
- 冲突查询返回最早一条冲突预约，仅用于文案，不参与后续写入。
- 文案不包含内部 ID/SQL/堆栈。

## 4. 未执行

| 项 | 原因 |
|----|------|
| `mypy` | CI 中非阻塞，本次未执行 |
| OpenAPI diff | 无路由/Schema 改动，未导出快照 |
| 全量 ruff | 仅检查本次文件，避免历史未提交文件噪声 |
