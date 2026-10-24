---
alwaysApply: false
globs: "apps/api/**/*.py"
---

# PostgreSQL / 模型与迁移

数据库：PostgreSQL 15 + SQLAlchemy 2.0（`mapped_column`），异步驱动 asyncpg。

## 模型

- 所有业务模型继承统一 `Base`（`app/shared/base_model.py`）；多租户表使用 `TenantMixin`（隔离规则见 `security/tenant-isolation.md`）。
- 模型聚合入口：`app/models.py`。新增模型必须在此注册，并在 `alembic/env.py` 中可被导入，否则 `--autogenerate` 检测不到。

## Schema 变更只走 Alembic

- 迁移目录：`apps/api/alembic/versions/`；唯一流程：
  1. 改模型 → 2. `uv run alembic revision --autogenerate -m "xxx"` → 3. **人工 review 生成文件**（autogenerate 常漏索引/枚举变更）→ 4. `uv run alembic upgrade head`。
- **禁止**绕过 Alembic 用手写 `ALTER TABLE` 等原始 DDL 改库结构；**禁止**直接修改生产数据库结构。
- 迁移文件不可用必须 `alembic downgrade -1` 后删除重做，不要在已应用的迁移上打补丁。

## 软删除

- 含 `deleted_at` 的表（users、courses、membership_card_products 等）采用软删除；查询必须显式加 `WHERE deleted_at IS NULL`。
- 租户自动注入（`tenant_query`）**不处理**软删除，不得假设框架会自动过滤。

## 约束与索引

- 业务唯一性必须由数据库约束兜底（Unique Constraint / Check），不能只靠应用层判断。
- 新增查询路径必须评估索引覆盖；外键、高频过滤列（尤其 `tenant_id` + 业务列组合）要有对应索引。
- 涉及并发写的表设计（容量计数、余额、状态）必须同时考虑行锁策略，见 `database/transaction.md`。
