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
