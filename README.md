# 舞蹈预约系统（dance-saas / class_booking_system）

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](https://github.com/lantercode/class_booking_system/actions)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Vue](https://img.shields.io/badge/vue-3.x-brightgreen.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

多租户多门店舞蹈教室预约系统：管理端 / 学员端 / 教师端三端 Web + 微信小程序，内置 AI 助手与实时推送。

## 快速访问

| 端 | 地址 |
|---|---|
| 管理后台 | https://admin.seplume.com |
| API 文档 | https://admin.seplume.com/api/docs |
| 体验账号 | 手机号 `13800000001`，密码 `password123`（学员 / 教师 / 管理员） |

## 核心功能

- **课程与排期**：课程分类、课程类型、班表与私教排期、容量与冲突检测
- **预约与签到**：在线预约、取消规则（按课程类型 `cancel_before_minutes` 配置）、课时扣减与回补、教师签到
- **会员卡**：期卡 / 次卡、发卡、冻结 / 解冻、续费预警通知
- **AI 助手**：多轮对话、MCP Tool 调用业务 Service、写操作必须用户确认、全链路 trace
- **实时推送**：站内通知 SSE / WebSocket，预约、签到、会员卡变更即时刷新
- **平台能力**：多租户隔离、RBAC 权限、JWT 双 Token、审计日志、后台任务与每日对账

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI、SQLAlchemy 2.0（async）、PostgreSQL、Redis、Alembic、APScheduler |
| AI | FastMCP（stdio）、火山方舟 Ark、Redis 会话、`ai_chat_trace` 观测 |
| 实时与任务 | SSE / WebSocket + Redis Pub/Sub、`job_queue` 持久化任务（Worker 灰度中） |
| Web | Vue 3、Element Plus、Pinia、vue-router、Vite |
| 小程序 | uni-app + Vue 3 + TypeScript（详见 [apps/miniapp/README.md](apps/miniapp/README.md)） |
| 工程化 | pnpm monorepo、uv、Docker Compose、Nginx、GitHub Actions |

## 项目结构

```text
class_booking_system/
├── apps/
│   ├── api/                # FastAPI 后端（业务在 src/app/modules/，AI 在 src/app/ai/）
│   ├── admin-web/          # 管理端（端口 5174）
│   ├── student-web/        # 学员端（端口 5173）
│   ├── teacher-web/        # 教师端（端口 5175）
│   └── miniapp/            # 微信小程序
├── packages/
│   ├── api-client/         # Web 三端共享 HTTP 客户端
│   ├── api-types/          # OpenAPI 生成类型（勿手改）
│   ├── config/             # 共享配置
│   └── utils/              # 共享工具
├── infra/                  # docker-compose、Nginx 配置
├── docs/                   # 规划、部署、交付文档
├── scripts/                # 工具脚本
```

## 快速开始

前置：Python 3.13 + [uv](https://docs.astral.sh/uv/)、Node.js 18+ + pnpm 10、Docker。

```bash
# 1. 启动基础设施（PostgreSQL + Redis）
pnpm db:up

# 2. 初始化后端依赖与环境变量
cd apps/api
uv sync
cp .env.example .env        # 按需修改数据库、Redis、JWT 等

# 3. 数据库迁移与种子数据
uv run alembic upgrade head
uv run python scripts/seed.py

# 4. 启动 API（http://localhost:8000/api/docs）
uv run uvicorn app.main:app --app-dir src --reload --host 0.0.0.0 --port 8000
```

另开终端启动前端（根目录执行）：

```bash
pnpm install
pnpm dev:student              # 学员端 http://localhost:5173
pnpm --filter admin-web dev   # 管理端 http://localhost:5174
pnpm --filter teacher-web dev # 教师端 http://localhost:5175
```

小程序（注意：**用 npm，不要用 pnpm**）：

```bash
cd apps/miniapp
npm install
npm run dev:mp-weixin   # 再用微信开发者工具打开 dist/dev/mp-weixin
```

## 测试与质量

```bash
# 后端
cd apps/api
uv run pytest tests/unit      # 单元测试
uv run ruff check src tests   # Lint
uv run mypy src               # 类型检查

# 集成测试：真实 Uvicorn(8765) + 真实 PostgreSQL/Redis，需先 pnpm db:up
uv run pytest tests/integration

# 前端类型与契约
pnpm gen:types                # 后端接口变更后重新生成 packages/api-types
```

测试规范见 `.trae/rules/testing/testing.md`（集成测试禁止改回 in-process client）。

## 部署与运维

- **触发方式**：push 到 `main` 自动执行 `.github/workflows/deploy.yml`（前端构建 → Nginx 刷新 → 数据库迁移 → 容器重建）。
- **生产环境**：服务器 `/opt/dance-saas`，API 容器 `dance-api`，PostgreSQL `dance-postgres`。
- **Nginx**：`infra/nginx/nginx.conf` 为线上生效配置（域名 + HTTPS），部署时拷贝到 `/etc/nginx/sites-available/dance-saas`；`infra/nginx/nginx.stage-a.conf` 是备案前 IP 直连备用，默认不启用。
- **环境变量**：`infra/docker/sync-env.sh` 把 `.env.prod.example` 的新键合并进 `.env.prod`（不覆盖已有值），仅在内容变化时备份，保留最近 5 份且权限 600。
- **Worker 灰度**：`TASK_WORKER_ENABLED=false` 为默认；开启后自动完成 / 人数不足取消改由 `job_queue` 执行，需观察对账日志（详见 `docs/ai/plans/03-scheduling-realtime.md`）。
- 详见 [docs/deployment.md](docs/deployment.md)。

## 文档地图

| 文档 | 内容 |
|---|---|
| [docs/ai/plans/README.md](docs/ai/plans/README.md) | AI 能力规划总览与当前阶段 |
| [docs/ai/plans/05-ai-agent-hands-on.md](docs/ai/plans/05-ai-agent-hands-on.md) | AI Agent 动手任务清单（学习/转型） |
| [docs/deployment.md](docs/deployment.md) | 生产部署细节与待办 |
| [docs/delivery/execution-board.md](docs/delivery/execution-board.md) | 交付执行看板 |
| [docs/delivery/history-t01-t16.md](docs/delivery/history-t01-t16.md) | 早期开发日志归档（2026-06 ~ 08，仅供回溯） |
| [.trae/rules/](.trae/rules/) | 架构、安全、AI、测试等工程规范 |

## 体验与联系

微信公众号（学员端服务通知 / 内容更新）：

![微信公众号二维码](docs/assets/wechat-qr.jpg)

## License

MIT License（`LICENSE` 文件待补）
