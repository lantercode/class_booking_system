---
alwaysApply: false
---

# 常用命令与本地开发注意事项

## 根目录（pnpm workspace）

```bash
pnpm install              # 安装所有 workspace 依赖
pnpm dev:student              # 学员端 http://localhost:5173
pnpm --filter admin-web dev   # 管理端 http://localhost:5174
pnpm --filter teacher-web dev # 教师端 http://localhost:5175
pnpm dev:api                  # 后端 http://localhost:8000（等价于下方 uvicorn 命令）
pnpm gen:types                # 由 OpenAPI 重新生成 packages/api-types（勿手改产物）
pnpm db:up / db:down          # 启停本地 PostgreSQL + Redis
pnpm db:logs                  # 查看基础设施日志
pnpm lint / test              # 编排各包 lint / 测试
```

## 后端 apps/api（用 uv，不要 pip install）

```bash
cd apps/api
uv sync
uv run uvicorn app.main:app --app-dir src --reload --host 0.0.0.0 --port 8000
uv run alembic revision --autogenerate -m "描述"
uv run alembic upgrade head
uv run python scripts/seed.py
uv run pytest tests/unit
uv run pytest tests/integration     # 需真实 DB/Redis，见 testing/testing.md
uv run ruff check src tests
uv run mypy src
uv run python scripts/ai_trace_stats.py  # AI 对话 trace 统计
```

## 小程序 apps/miniapp

**必须用 npm，不要用 pnpm**（lockfile 与依赖提升方式不同，混用会导致依赖解析不一致）。

```bash
cd apps/miniapp
npm install
npm run dev:mp-weixin    # 微信开发者工具打开 dist/dev/mp-weixin
npm run build:mp-weixin
```

## 本地开发注意事项

- API 基址 `http://localhost:8000`（不要尾斜杠）；Swagger `/api/docs`，业务接口统一 `/api/v1` 前缀，集合端点不加尾斜杠。
- 端口分配：8000 API、5173 学员端、5174 管理端、5175 教师端、8765 集成测试专用。
- 登录种子账号：手机号 `13800000001`，密码 `password123`。
- `pkill -f uvicorn` 匹配到进程并成功终止时返回码为 1 属正常现象，不是失败。
- Web 三端 baseURL 为相对路径 `/api/v1`；小程序用 `VITE_API_BASE_URL` 绝对地址。
