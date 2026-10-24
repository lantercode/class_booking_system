# F4.4 — 静态验证报告

> 日期：2026-10-02

## 1. py_compile

```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
  src/app/modules/booking/models.py \
  src/app/modules/schedule/models.py \
  src/app/modules/membership/models.py \
  alembic/versions/f44ab1c2d3e4_add_status_check_constraints.py \
  tests/integration/test_status_check_constraints.py && echo "COMPILE_OK_ALL"
```

实际执行：

```
$ cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
    src/app/modules/booking/models.py \
    src/app/modules/schedule/models.py \
    src/app/modules/membership/models.py \
    alembic/versions/f44ab1c2d3e4_add_status_check_constraints.py \
    tests/integration/test_status_check_constraints.py && echo "COMPILE_OK_ALL"
COMPILE_OK_ALL
```

> IDE 报 "无法解析导入 sqlalchemy/pytest/app.*" 为 linter 未识别 venv 的误报，py_compile 在 venv 下通过。

## 2. 模型与 migration 一致性核查

### 2.1 bookings

```bash
grep -n "CheckConstraint\|ck_bookings_status" apps/api/src/app/modules/booking/models.py
```

| 行 | 代码 | 结论 |
|----|------|------|
| L5 | `from sqlalchemy import ..., CheckConstraint, ...` | import 已补 |
| L67-70 | `CheckConstraint("status IN (1, 2, 3, 4, 5)", name="ck_bookings_status")` | 模型声明约束 |

migration：
- `op.create_check_constraint("ck_bookings_status", "bookings", "status IN (1, 2, 3, 4, 5)")` → 与模型一致。

### 2.2 course_schedules

```bash
grep -n "CheckConstraint\|ck_course_schedules_status" apps/api/src/app/modules/schedule/models.py
```

| 行 | 代码 | 结论 |
|----|------|------|
| L66-69 | `CheckConstraint("status IN (1, 2, 3)", name="ck_course_schedules_status")` | 模型声明约束 |

migration：
- `op.create_check_constraint("ck_course_schedules_status", "course_schedules", "status IN (1, 2, 3)")` → 与模型一致。

### 2.3 membership_cards

```bash
grep -n "CheckConstraint\|ck_membership_cards_status" apps/api/src/app/modules/membership/models.py
```

| 行 | 代码 | 结论 |
|----|------|------|
| L228-231 | `CheckConstraint("status IN (0, 1, 2, 3, 6)", name="ck_membership_cards_status")` | 模型声明约束 |

migration：
- `op.create_check_constraint("ck_membership_cards_status", "membership_cards", "status IN (0, 1, 2, 3, 6)")` → 与模型一致。

## 3. 分层合规检查

```bash
# 确认 Service/Repository/Router/schemas 零改动
git status --short -- \
  apps/api/src/app/modules/booking/service.py \
  apps/api/src/app/modules/booking/repository.py \
  apps/api/src/app/modules/booking/router.py \
  apps/api/src/app/modules/booking/schemas.py \
  apps/api/src/app/modules/schedule/service.py \
  apps/api/src/app/modules/schedule/repository.py \
  apps/api/src/app/modules/schedule/router.py \
  apps/api/src/app/modules/schedule/schemas.py \
  apps/api/src/app/modules/membership/service.py \
  apps/api/src/app/modules/membership/repository.py \
  apps/api/src/app/modules/membership/router.py \
  apps/api/src/app/modules/membership/schemas.py
# 无输出（这些文件未改动）
```

| 规则 | 检查 | 结果 |
|------|------|------|
| Service/Repository 零改动 | `git status` 显示 booking/schedule/membership 的 service/repository/router/schemas 均未动 | 通过 |
| migration 走 Alembic | 用 `op.execute` + `op.create_check_constraint` / `op.drop_constraint`，非手写 SQL 脚本 | 通过 |
| 事务边界 | 越界校验 + ADD CONSTRAINT 在同一 migration upgrade（alembic `Will assume transactional DDL`） | 通过 |
| 不裸 SQL 直写业务数据 | Service/Repository 无改动；migration 内 SQL 是越界统计校验，非业务读写 | 通过 |
| 租户隔离 | Check 约束不涉及租户过滤；`TenantAwareRepository` 语义不变 | 通过 |
| RBAC | 无端点变更 | 通过 |
| 认证 | 无端点变更 | 通过 |
| AI 边界 | 不涉及 MCP（无 Tool 变更） | 通过 |

## 4. 改动落点核查（grep 改动面白名单）

```bash
git status --short
```

本 Feature 实际触碰：

| 文件 | 本 Feature 实际变化 | 审查结论 |
|------|------|---------|
| `apps/api/alembic/versions/f44ab1c2d3e4_add_status_check_constraints.py` | 新建 migration | 越界校验 + 3 个 Check 约束；down_revision=f42cd3e4f5a6 |
| `apps/api/src/app/modules/booking/models.py` | import 补 `CheckConstraint`；`__table_args__` 补 `ck_bookings_status` | 模型与 migration 一致 |
| `apps/api/src/app/modules/schedule/models.py` | `__table_args__` 补 `ck_course_schedules_status` | 模型与 migration 一致 |
| `apps/api/src/app/modules/membership/models.py` | `__table_args__` 补 `ck_membership_cards_status` | 模型与 migration 一致 |
| `apps/api/tests/integration/test_status_check_constraints.py` | 新建 | 18 用例覆盖 AC-1~AC-10 |

Service / Repository / Router / schemas / OpenAPI / 前端 / MCP 均未改动。

## 5. revision 链核查

```bash
cd apps/api && PYTHONPATH=src .venv/bin/alembic heads
# 本 Feature 前：f42cd3e4f5a6 (head)   ← F4.2 后
# 本 Feature 后：f44ab1c2d3e4 (head)   ← 单 head（无分叉）
```

- `down_revision="f42cd3e4f5a6"` 指向 F4.2 后的唯一 head。
- 新 migration 应用后 `alembic heads` 仍为单 head `f44ab1c2d3e4`，无分叉。

## 6. DB 事实核查（migration 前后对比）

| 指标 | migration 前 | migration 后 |
|------|-------------|-------------|
| bookings 总数 | 11 | 11（不变） |
| course_schedules 总数 | 33 | 33（不变） |
| membership_cards 总数 | 17 | 17（不变） |
| 越界 status 行数（三表） | 0 | 0（不变） |
| `ck_bookings_status` | 不存在 | 存在，`CHECK ((status = ANY (ARRAY[1, 2, 3, 4, 5])))` |
| `ck_course_schedules_status` | 不存在 | 存在，`CHECK ((status = ANY (ARRAY[1, 2, 3])))` |
| `ck_membership_cards_status` | 不存在 | 存在，`CHECK ((status = ANY (ARRAY[0, 1, 2, 3, 6])))` |
| alembic_version | `f42cd3e4f5a6` | `f44ab1c2d3e4` |

实测 SQL：
```sql
SELECT pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid='bookings'::regclass AND conname='ck_bookings_status';
-- → CHECK ((status = ANY (ARRAY[1, 2, 3, 4, 5])))

SELECT pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid='course_schedules'::regclass AND conname='ck_course_schedules_status';
-- → CHECK ((status = ANY (ARRAY[1, 2, 3])))

SELECT pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid='membership_cards'::regclass AND conname='ck_membership_cards_status';
-- → CHECK ((status = ANY (ARRAY[0, 1, 2, 3, 6])))
```

## 7. migration 可逆性验证（AC-13 手动）

```bash
cd apps/api && PYTHONPATH=src .venv/bin/alembic downgrade -1
# → Running downgrade f44ab1c2d3e4 -> f42cd3e4f5a6
# 验证：三约束不存在、alembic_version=f42cd3e4f5a6
# 实测：ck_*_status count=0, alembic_version=f42cd3e4f5a6

cd apps/api && PYTHONPATH=src .venv/bin/alembic upgrade head
# → Running upgrade f42cd3e4f5a6 -> f44ab1c2d3e4
# 验证：三约束存在、alembic_version=f44ab1c2d3e4
# 实测：ck_bookings_status=OK, ck_course_schedules_status=OK, ck_membership_cards_status=OK
```

往返成功，证明 upgrade/downgrade 均可重复执行。

## 8. 契约一致性

- OpenAPI 路径 / 方法 / 请求体 / 响应模型全部不变（无端点变更）。
- 模型列 `status` 类型仍为 `SmallInteger`（nullable=False），仅新增 CheckConstraint → DTO 字段集合不变。
- 前端 4 端影响评估：admin-web / teacher-web / student-web / miniapp 不直接感知 DB Check 约束；三表对应端点契约不变 → 均不涉及。
- 无需 `pnpm gen:types`。

## 9. 异常处理一致性

- DB 层 Check 违反抛 `IntegrityError`（SQLAlchemy），不直接透传前端。
- 非法 status 写入若由业务缺陷触发，经全局异常处理器返回统一信封 `{code:500, msg, data:null}`，不回显 SQL / traceback（见 AC-4/5/6 测试断言）。
