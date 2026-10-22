# F6.5 静态验证报告

> 日期：2026-10-22
> 方式：命令实跑 + 代码审查 + mtime 范围核对
> 结论：A-1 ~ A-11 全部 PASS；其中 A-11 有 2 处已说明的附加文件（非代码扩围）。

## 1. 命令与结果

| # | 检查 | 命令 | 结果 |
|---|------|------|------|
| S1 | 语法 | `python3 -m py_compile`（8 个改动文件） | PASS（`PY_COMPILE_OK`） |
| S2 | Lint | `.venv/bin/ruff check`（booking/schedule/membership service + 2 测试 + support） | **All checks passed** |
| S3 | 迁移往返 | `alembic downgrade -1` → `alembic upgrade head` | PASS（`f6a5b4c3d2e1` → `a7b8c9d0e1f2` → head） |
| S4 | 迁移漂移 | `alembic check` | `No new upgrade operations detected.` |
| S5 | 契约生成 | `grep reschedule packages/api-types/*` | 端点存在于 `openapi.json` 与 `schema.d.ts`，未手改 |
| S6 | 范围 | 11:50 后 mtime 清单 | PASS（见 §3） |

> S2 首轮命中 `booking/models.py` I001（新增 `CheckConstraint` 使 import 行超长），已按 ruff 建议改为多行导入；复跑全绿。

## 2. 验收标准（A 组）

| AC | 结果 | 证据 |
|----|------|------|
| A-1 可编译 | PASS | S1 |
| A-2 Ruff | PASS | S2 |
| A-3 分层 | PASS | `router.py:184-211` 仅参数/依赖/调用/响应；模式判定、状态校验、容量调整、回补/扣次均在 Service |
| A-4 租户 | PASS | `BookingRescheduleRepository(TenantAwareRepository)`（`repository.py:422`）；`find_overlapping_active_booking` JOIN 场景显式叠加 `Booking.tenant_id` 并有注释（`repository.py:215-219`） |
| A-5 无裸 SQL | PASS | 唯一 `text()` 为 `pg_advisory_xact_lock` 与模型索引表达式；无业务读写裸 SQL |
| A-6 DTO | PASS | 请求体仅 `new_schedule_id` / `new_membership_card_id` / `reason`；`tenant_id` / `student_id` 来自 `current_user` |
| A-7 路由形态 | PASS | `POST /bookings/{booking_id}/reschedule`，无尾斜杠 |
| A-8 OpenAPI / 类型 | PASS | S5；生成物仅由 `pnpm gen:types` 更新 |
| A-9 迁移可用 | PASS | S3 + S4 |
| A-10 安全输出 | PASS | 错误统一走 `BusinessException` 友好文案；`IntegrityError` 分支只输出中文提示，不回显 SQL/堆栈 |
| A-11 范围 | PASS（含说明） | 代码与测试均在预期白名单内；附加 `tests/membership_support.py`（测试支撑）与 `docs/features/F6.0.../open-decisions.md`（决策台账同步） |

## 3. 实际改动清单（按 mtime）

```text
apps/api/src/app/modules/booking/models.py
apps/api/src/app/modules/booking/repository.py
apps/api/src/app/modules/booking/service.py
apps/api/src/app/modules/booking/schemas.py
apps/api/src/app/modules/booking/router.py
apps/api/src/app/modules/schedule/repository.py
apps/api/src/app/modules/schedule/service.py
apps/api/src/app/modules/membership/service.py
apps/api/alembic/versions/f6a5b4c3d2e1_add_booking_reschedules.py   （新增）
apps/api/tests/integration/test_booking_reschedule.py               （新增）
apps/api/tests/integration/test_booking_reschedule_concurrency.py   （新增）
apps/api/tests/membership_support.py                                （测试支撑）
packages/api-types/openapi.json / schema.d.ts                       （生成物）
docs/features/F6.5-atomic-reschedule/*                              （产物）
docs/features/F6.0-membership-card-prototype/open-decisions.md      （D7 状态同步）
docs/engineering/task-records/20261022-F6.5-atomic-reschedule.md    （遥测）
```

未改动：`schedule/service.py:341-379` 排期取消流程、`membership/repository.py`、任何前端应用与 `packages/api-client`。

## 4. 代码审查要点

- **锁序唯一入口**：改期只从 `reschedule_booking` 进入；Repository 方法不自行 commit，事务边界唯一。
- **禁止降级放行**：无 feature flag、无 bypass 分支；目标排期/卡校验失败一律抛错回滚。
- **fail-closed**：回补/扣次异常向上抛，`except` 先 `rollback()` 再转换异常。
- **审计表无业务 FK**：避免与排期硬删除冲突；`tenant_id` 保留外键与索引。
- **未触碰既有规则**：取消窗口文案与行为不变（仅抽取函数）；签到/完成/取消链路未改锁。
- **身份可信**：`user_id`、`tenant_id` 只取自 `get_current_user` 注入的 payload。

## 5. 未执行

| 项 | 原因 |
|----|------|
| `mypy` | CI 非阻塞，本次未执行 |
| 前端 `vue-tsc` / 小程序构建 | 本 Feature 无前端消费者，F6.10/F6.11 执行 |
| 全量 `pytest` | 基线组按定向 + 回归集交付 |
| 全仓库 ruff | 仅检查本次文件，避免既有未提交文件噪声 |
