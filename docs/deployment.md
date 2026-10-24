# Deployment

## Purpose

本文档描述 class_booking_system 的部署架构，包括 Docker 容器化配置、开发/生产环境差异、Nginx 反向代理、GitHub Actions CI/CD 流程及生产 ECS 部署步骤。

## Current Implementation

### 环境划分

| 环境 | 配置文件 | 启动方式 |
|------|----------|----------|
| 本地开发 | `infra/docker/docker-compose.yml` | `docker compose up` |
| 生产 | `infra/docker/docker-compose.prod.yml` | CI/CD 自动部署到 ECS |

### 服务器拓扑

```mermaid
graph TD
    subgraph Client["客户端"]
        AdminWeb[admin-web<br/>Vue3 SPA]
        Miniapp[微信小程序]
    end

    subgraph ECS["阿里云 ECS 服务器"]
        subgraph Nginx["Nginx 反向代理"]
            NAdmin[admin.yourdomain.com<br/>admin-web 静态 + /api 反向代理]
            NApi[api.yourdomain.com<br/>纯 API 反代]
        end

        subgraph Containers["Docker 容器"]
            PG[PostgreSQL 15]
            Redis[Redis 7]
            API[FastAPI / Uvicorn]
        end

        subgraph Volumes["Docker Volumes"]
            VPG[(pgdata)]
            VRedis[(redisdata)]
        end
    end

    AdminWeb -- HTTPS --> NAdmin
    Miniapp -- HTTPS --> NApi
    NAdmin -- 静态文件 --> /var/www/admin
    NAdmin -- /api/* 反代 --> API
    NApi -- 全部反代 --> API
    API --> PG
    API --> Redis
    PG -- 数据持久化 --> VPG
    Redis -- 数据持久化 --> VRedis

    style Client fill:#e1f5fe
    style ECS fill:#fff9c4
    style Containers fill:#c8e6c9
```

### Docker Compose 服务对比

| 服务 | 开发环境 | 生产环境 |
|------|----------|----------|
| **PostgreSQL** | `postgres:15-alpine` | 同 |
| 端口暴露 | `5432:5432`（外部访问） | 无（仅容器内） |
| 用户名密码 | 硬编码 `dance/dance_dev_pass` | 从 `.env.prod` 读取 |
| Healthcheck | ✅ `pg_isready` | ✅ 同 |
| **Redis** | `redis:7-alpine` | 同 |
| 端口暴露 | `6379:6379`（外部访问） | 无（仅容器内） |
| Healthcheck | ✅ `redis-cli ping` | ✅ 同 |
| **API** | 无端口映射（dev 一般直接运行本地） | `127.0.0.1:8000:8000`（仅本机访问） |
| 依赖 | redis: healthy | postgres + redis 都需 healthy |
| 环境变量 | `DATABASE_URL`, `REDIS_URL` 硬编码 | `APP_ENV=production`, `JWT_SECRET`, `CORS_ORIGINS` 等 |

### Dockerfile 详细信息

| 层 | 操作 |
|------|------|
| 基础镜像 | `python:3.12-slim` |
| apt | build-essential, curl（清华源加速） |
| pip | 安装 `uv`（清华 pypi 源） |
| WORKDIR | `/app` |
| COPY | pyproject.toml + uv.lock → `uv sync --frozen --no-dev` |
| COPY | 源码到 /app |
| ENV | `PYTHONPATH=/app/src`, `PYTHONUNBUFFERED=1` |
| EXPOSE | 8000 |
| CMD | `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` |

### Nginx 反向代理

| 域名 | 用途 | SSL | 反代目标 |
|------|------|-----|----------|
| `admin.yourdomain.com` | 管理后台（Vue3 SPA） | Let's Encrypt | 静态 `/var/www/admin` + `/api/*` → `127.0.0.1:8000` |
| `api.yourdomain.com` | 公开 API（小程序端） | Let's Encrypt | 全部 → `127.0.0.1:8000` |

关键配置：
- `client_max_body_size 20M`（API 上传图片）
- SPA `try_files $uri $uri/ /index.html`（admin）
- `proxy_read_timeout 60s`
- HTTPS 自动跳 301（HTTP → HTTPS）

### GitHub Actions CI 流程

| Job | 触发 | runs-on | services | 步骤 |
|-----|------|---------|----------|------|
| backend | push to main | ubuntu-latest | PostgreSQL 15 + Redis 7 | Ruff Lint → Mypy Type Check → Alembic Upgrade → Pytest |
| frontend | push to main | ubuntu-latest | - | ESLint Lint → pnpm build all apps |

CI 使用 `astral-sh/setup-uv@v4` 安装 uv。

### GitHub Actions CD 流程

| 项目 | 值 |
|------|------|
| 触发 | `push` 到 `main` 或 `production` 分支 |
| runners | ubuntu-latest |
| 部署方式 | `appleboy/ssh-action@v1` SSH 连接 ECS |
| 执行时长 | 30 分钟 timeout |
| 服务器路径 | `/opt/dance-saas` |

部署步骤：

```mermaid
flowchart TD
    Start["push main/production"] --> SSH["SSH 到 ECS"]
    SSH --> Pull["git checkout + git pull origin main"]
    Pull --> CheckEnv{.env.prod 存在?}
    CheckEnv -- 否 --> CreateEnv["从 .env.example 创建"]
    CheckEnv -- 是 --> BuildFE
    CreateEnv --> BuildFE
    BuildFE["pnpm install --no-frozen-lockfile<br/>pnpm build admin-web<br/>cp dist → /var/www/admin"]
    BuildFE --> Nginx["cp nginx.conf → /etc/nginx<br/>sed 替换域名占位符<br/>nginx -t && reload"]
    Nginx --> BuildImage["docker compose build api"]
    BuildImage --> Up["docker compose up -d api"]
    Up --> WaitContainer["等待容器 running (最多 30s)"]
    WaitContainer --> Alembic["docker exec alembic upgrade head"]
    Alembic --> Health["curl /api/v1/common/health"]
    Health --> Tag["docker tag commit_sha"]
    Tag --> Prune["docker image prune -f"]
    Prune --> Done["部署完成 ✅"]
```

## Architecture

### 一键开发环境启动

```bash
cd infra/docker
docker compose up -d
# PostgreSQL 5432, Redis 6379 已暴露
# 然后在 apps/api 目录运行:
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

> 开发环境 docker-compose.yml 不启动 API 服务，因为一般本地直接用 `uv run uvicorn` 跑带 hot-reload 的开发服务器。

### 生产部署容器启动顺序

```mermaid
flowchart LR
    PG[PostgreSQL<br/>healthcheck OK] --> API1
    Redis[Redis<br/>healthcheck OK] --> API1
    API1[API Container<br/>docker compose up -d] --> WaitHealth{容器 running?}
    WaitHealth -- 是 --> Alembic["docker exec alembic upgrade head"]
    WaitHealth -- 否 --> Fail["❌ 退出"]
    Alembic --> HealthCheck["curl health endpoint"]
    HealthCheck -- 200 OK --> Tag["docker tag commit-sha"]
    HealthCheck -- 失败 --> Fail2["❌ 退出并输出 logs"]
```

## Important Rules

### 生产环境必须的环境变量

| 变量 | docker-compose.prod.yml 引用 | 说明 |
|------|-------------------------------|------|
| POSTGRES_USER | ✅ | 数据库用户 |
| POSTGRES_PASSWORD | ✅ | 数据库密码 |
| POSTGRES_DB | ✅ | 数据库名 |
| JWT_SECRET | ✅ | JWT 签名密钥 |
| CORS_ORIGINS | ✅ | 允许的跨域来源（逗号分隔） |
| WECHAT_APP_ID | ✅ | 微信 AppID |
| WECHAT_SECRET | ✅ | 微信 AppSecret |
| REDIS_URL | docker-compose 内部生成 | 不需要外部配置 |
| DATABASE_URL | docker-compose 内部生成 | 不需要外部配置 |

### GitHub Secrets

| Secret | 用途 |
|--------|------|
| ECS_HOST | ECS 服务器 IP |
| ECS_USER | SSH 用户名 |
| ECS_SSH_KEY | SSH 私钥内容 |

### 安全要点

1. 生产 API 端口绑定 `127.0.0.1:8000`（仅本机可访问），外部通过 Nginx 反代
2. PostgreSQL 和 Redis 端口不在生产环境暴露到主机
3. Nginx 自动 HTTPS 跳转（301）
4. SSL 使用 Let's Encrypt，admin 域名证书同时覆盖 api 域名（SAN）
5. Docker 镜像使用清华源加速（apt + pip），降低构建时间
6. 密码和密钥只在 `.env.prod` 和 GitHub Secrets 中存在

## Dependencies

### 开发依赖（Docker）

| 依赖 | 版本 |
|------|------|
| PostgreSQL | 15-alpine |
| Redis | 7-alpine |
| Python | 3.12-slim |
| uv | latest（通过 pip 安装） |

### CI/CD 依赖

| 工具 | 版本 | 用途 |
|------|------|------|
| astral-sh/setup-uv | v4 | CI 安装 uv |
| pnpm/action-setup | v4 | CI 安装 pnpm |
| actions/setup-node | v4 | CI Node 22 |
| appleboy/ssh-action | v1 | CD SSH 部署 |
| actions/checkout | v4 | Checkout 代码 |

### 服务器依赖

| 软件 | 版本 | 用途 |
|------|------|------|
| Docker | ≥ 24 | 容器运行 |
| Docker Compose | ≥ 2.20 | 容器编排 |
| Nginx | ≥ 1.24 | 反向代理 |
| certbot | - | Let's Encrypt 证书 |
| git | - | pull 代码 |

## Common Failure Points

1. **CI 数据库 URL 硬编码**：ci.yml 中 `DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test`，如果 CI services 配置变动（密码不匹配）会导致 Alembic 迁移和 Pytest 失败
2. **Docker build 上下文路径**：`docker build -f ../../apps/api/Dockerfile` 上下文是 `infra/docker`，但 Dockerfile 中 `COPY pyproject.toml uv.lock ./` 需要从 build context 可见——需确认路径正确
3. **deploy.yml 中 Alembic 在 API 容器启动后执行**：如果 Alembic 脚本依赖某些运行时环境变量（`DATABASE_URL`），容器内部的 env 必须正确注入
4. **admin-web 部署路径硬编码 `/var/www/admin`**：deploy.yml 每次都 `rm -rf /var/www/admin/*` + `cp -r dist/*`，如果用户有自定义文件会被清除
5. **Git pull 使用 HTTPS**：`git remote set-url origin https://github.com/...`，GitHub Actions runner 需要有服务器上的 git credentials（可能通过 `.netrc`）
6. **Nginx SSL 证书需要提前手动申请**：deploy.yml 只配置 nginx.conf，不自动申请 certbot 证书
7. **`uv sync --frozen --no-dev`**：生产镜像不安装 dev 依赖，如果 Alembic 在 dev 依赖里，会导致 `docker exec alembic` 找不到命令
8. **deploy.yml 注释掉了一些步骤**（`# Replace lines 103-119 with:`），说明文件可能有手动编辑过，需要确认当前完整内容

## TODO / Known Issues

- [ ] docker-compose.prod.yml 的 api 端口绑定 `127.0.0.1:8000:8000`，但 nginx.conf 反代目标是 `127.0.0.1:8000`——确认一致
- [ ] deploy.yml 中注释掉了一些代码块（`# Replace lines 103-119 with:`），可能有残留
- [ ] 生产环境 Redis 密码未配置（docker-compose.prod.yml 无 Redis requirepass），建议加上
- [ ] PostgreSQL 持久化未配置备份策略（pgdump / WAL 归档）
- [ ] CI 中 `mypy continue-on-error: true` 跳过类型错误，应该改为严格模式
- [ ] deploy.yml 中 `pnpm install --no-frozen-lockfile`，生产环境应使用 `--frozen-lockfile` 确保版本可追溯
- [ ] Dockerfile 使用清华源但注释说可能失败，没有 fallback 机制
- [ ] 没有看到 `docker-compose.prod.yml` 中 Redis 的持久化策略（是否需要 AOF 或 RDB 配置）
- [ ] 日志未配置集中化（ELK / Loki），当前直接 `docker logs`
- [ ] 没有看到监控告警配置（Prometheus / Grafana）
- [ ] admin-web 构建后直接 cp 到 `/var/www/admin`，没有 sha256 校验或 hash 文件——浏览器可能拿到缓存旧版本
- [ ] Alembic 迁移在容器启动后执行，但如果回滚（downgrade）场景未覆盖
