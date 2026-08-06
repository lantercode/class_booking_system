# Dance SaaS API

FastAPI 后端。

## 本地启动

```bash
# 装依赖（用 uv）
uv sync

# 启动开发服务器
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir src

# 或在 Monorepo 根用 pnpm
pnpm --filter api dev
```

健康检查：

```bash
curl http://localhost:8000/api/v1/common/health
```

文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc:      http://localhost:8000/redoc

## 数据库迁移

使用 Alembic 管理数据库版本。

```bash
# 生成迁移文件（自动检测模型变更）
alembic revision --autogenerate -m "描述你的变更"

# 执行迁移（应用到数据库）
alembic upgrade head

# 回滚一步
alembic downgrade -1

# 查看当前版本
alembic current

# 查看迁移历史
alembic history
```

> 注意：新增模型后，需要在 `alembic/env.py` 中导入对应的 Model 类，否则 autogenerate 无法检测到新表。