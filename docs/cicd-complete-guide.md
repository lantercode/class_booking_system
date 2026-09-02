# 舞蹈机构 SaaS 项目：CI/CD、Docker、Nginx、DNS、HTTPS 完整架构解析

## 一、文档目标

本文档用于指导开发者结合舞蹈机构 SaaS 项目的真实生产环境，系统分析并理解完整的 CI/CD 与生产部署流程。

核心目标不是泛泛学习 DevOps，而是理解：

> 从本地执行 `git push` 开始，代码如何经过 GitHub、GitHub Actions、SSH、阿里云 ECS、Docker、Nginx、DNS、HTTPS，最终让用户访问前端和 FastAPI API。

最终应能够做到：

- 看懂现有 CI/CD 配置
- 理解一次 `git push` 后发生的完整过程
- 手动完成生产部署
- 判断代码是否真正更新
- 判断 Docker Image / Container 是否更新
- 判断数据库结构是否更新
- 排查 GitHub Actions、SSH、Docker、FastAPI、PostgreSQL、Nginx、DNS、HTTPS 问题
- 理解 IP → 域名 → HTTPS 的迁移过程
- 理解并设计适合当前项目的生产级 CI/CD

---

# 二、项目真实背景

## 1. 后端技术栈

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Redis
- uv
- Docker
- Docker Compose
- Alembic

## 2. 前端技术栈

- Vue3
- Vite
- TypeScript

## 3. 生产服务器

- 阿里云 ECS
- Ubuntu
- Nginx
- Docker / Docker Compose

## 4. 当前生产容器

服务器执行：

```bash
docker ps
```

当前类似：

```text
dance-api
dance-postgres
dance-redis
```

关系：

```text
dance-api
    ↓
FastAPI :8000

dance-postgres
    ↓
PostgreSQL 15
    ↓
docker_pgdata

dance-redis
    ↓
Redis 7
    ↓
docker_redisdata
```

---

# 三、当前访问方式与未来规划

## 1. 当前前端

当前前端通过 ECS 公网 IP 访问：

```text
http://106.14.206.226/login
```

请求路径：

```text
浏览器
 ↓
106.14.206.226:80
 ↓
Nginx
 ↓
前端 Vue
```

## 2. 当前后端

后端规划使用：

```text
https://api.seplume.com
```

最终 API 请求：

```text
浏览器
 ↓
https://api.seplume.com
 ↓
DNS
 ↓
106.14.206.226
 ↓
Nginx :443
 ↓
127.0.0.1:8000
 ↓
Docker
 ↓
dance-api
 ↓
FastAPI
```

## 3. 前端域名

DNS 已配置：

```text
@       A    106.14.206.226
admin   A    106.14.206.226
api     A    106.14.206.226
```

对应：

```text
seplume.com
    ↓
106.14.206.226

admin.seplume.com
    ↓
106.14.206.226

api.seplume.com
    ↓
106.14.206.226
```

未来前端可以规划为：

```text
https://seplume.com/login
```

或者：

```text
https://admin.seplume.com/login
```

---

# 四、完整生产架构

```text
                         用户浏览器
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ↓ (当前)                        ↓ (未来 Stage B)
   http://106.14.206.226              admin.seplume.com / api.seplume.com
              │                               │
              ↓                               ↓
         Nginx :80 (ECS)                  Nginx :443 (SSL)
              │                               │
    ┌─────────┴─────────┐           ┌─────────┴─────────┐
    │                   │           │                   │
    ↓                   ↓           ↓                   ↓
/var/www/admin/    location /   server_name        server_name
(前端静态文件)       /api/      admin.seplume.com  api.seplume.com
                          ↓           ↓                   ↓
                    127.0.0.1:8000   /api/ → 127.0.0.1:8000
                          │
                          ↓
                   Docker Compose
                   (docker-compose.prod.yml)
                          │
                  ┌───────┼───────┐
                  ↓       ↓       ↓
             dance-api  dance-  dance-
             (FastAPI)  postgres redis
                  │       │       │
                  │    pgdata  redisdata
                  │    (Vol)   (Vol)
                  ↓
             SQLAlchemy
                  ↓
            PostgreSQL / Redis
```

CI/CD 则位于发布链路：

```text
开发者
   ↓
git push
   ↓
GitHub
   ↓
GitHub Actions
   ↓
CI
   ↓
Docker Build / Test
   ↓
SSH
   ↓
ECS
   ↓
Docker Compose
   ↓
dance-api
   ↓
FastAPI
   ↓
Nginx
   ↓
用户
```

---

# 五、CI/CD 核心概念

## 1. CI：持续集成

CI（Continuous Integration）的核心：

```text
代码提交
 ↓
自动检查
 ↓
自动测试
 ↓
构建
```

当前项目包括：

- 安装 Python
- 安装 uv
- 安装依赖
- Ruff
- pytest
- MyPy
- Docker build

## 2. CD：持续交付 / 持续部署

CD 的核心：

```text
代码通过 CI
 ↓
发布到生产环境
 ↓
更新服务
 ↓
健康检查
```

链路：

```text
GitHub Actions Runner
        │
        │ SSH
        ↓
      ECS
        ↓
Docker Compose
        ↓
dance-api
```

---

# 六、一次 git push 到生产的完整流程

假设：

```bash
git add .
git commit -m "feat: update course API"
git push origin main
```

完整流程：

```
┌─────────────────────────────────────────────────────────────────┐
│ ① 本地开发电脑 (你的 Mac)                                        │
│                                                                 │
│  $ git add .                                                    │
│  $ git commit -m "feat: update course API"                      │
│  $ git push origin main                                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTPS + Git 协议
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ ② GitHub 仓库                                                    │
│                                                                 │
│  接收代码 → 更新 main 分支                                       │
│  检测到两个 workflow:                                            │
│  - .github/workflows/ci.yml → 触发 CI                           │
│  - .github/workflows/deploy.yml → 触发 CD                       │
└──────────────────────┬──────────────────────────────────────────┘
                       │
            ┌──────────┴──────────┐
            ↓                     ↓
┌──────────────────┐    ┌──────────────────┐
│   CI (ci.yml)    │    │  CD (deploy.yml) │
│                  │    │                  │
│  在 GitHub       │    │  在 GitHub       │
│  Runner 执行:    │    │  Runner 执行:    │
│                  │    │                  │
│  Backend:        │    │  SSH 连接 ECS    │
│  - checkout      │    │  - git pull      │
│  - uv sync       │    │  - pnpm build    │
│  - ruff check    │    │  - Nginx reload  │
│  - mypy          │    │  - alembic       │
│  - pytest        │    │  - docker build  │
│                  │    │  - health check  │
│  Frontend:       │    │                  │
│  - checkout      │    │                  │
│  - pnpm install  │    │                  │
│  - pnpm build    │    │                  │
└──────────────────┘    └────────┬─────────┘
                                 │ SSH (加密通道)
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│ ③ 阿里云 ECS (Ubuntu 22.04, 2C4G)                                │
│                                                                 │
│  以 root 身份执行 deploy.yml 中的 script:                        │
│                                                                 │
│  Step 0: 记录 Commit SHA                                        │
│  Step 1: 配置 Git (HTTP/1.1, 大缓冲区)                           │
│  Step 2: 确保远程仓库是 HTTPS                                   │
│  Step 3: git pull origin main (重试 3 次)                        │
│  Step 4: 创建 .env.prod (如果不存在)                             │
│  Step 5: pnpm install + pnpm build → /var/www/admin/            │
│  Step 6: 写入 Nginx 配置 + reload                               │
│  Step 7: alembic upgrade head (数据库迁移)                       │
│  Step 8: docker compose up -d --build                           │
│         docker tag dance-saas-api:$COMMIT_SHA                   │
│  Step 9: curl /health 健康检查 (最多 30 秒)                      │
│  Step 10: docker image prune -f                                 │
│                                                                 │
│  全部成功 → SSH 断开 → GitHub Actions 标记 ✅                    │
│  健康检查失败 → 输出日志 → exit 1 → 标记 ❌                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ ④ Docker Container 更新                                          │
│                                                                 │
│  docker compose up -d --build 做了什么:                          │
│                                                                 │
│  a. 读取 infra/docker/docker-compose.prod.yml                   │
│  b. 读取 .env.prod 环境变量                                      │
│  c. 对 api 服务:                                                 │
│     - 发现 build 配置 → 执行 docker build                        │
│     - 使用 apps/api/Dockerfile                                  │
│     - 构建新镜像                                                 │
│  d. 停止旧 dance-api 容器                                        │
│  e. 用新镜像创建新 dance-api 容器                                │
│  f. postgres 和 redis 不重建 (用 image 而非 build)               │
│                                                                 │
│  结果: dance-api 运行最新代码, 数据库数据保留                     │
│        镜像被打上 Commit SHA 标签 (dance-saas-api:abc1234)       │
└─────────────────────────────────────────────────────────────────┘
```

每一步都应该明确：

- 执行位置
- 执行者
- 执行命令
- 输入
- 输出
- 成功标准
- 失败后的排查位置

---

# 七、必须区分的五个运行环境

整个 CI/CD 分析必须明确区分：

```text
① 本地电脑

② GitHub

③ GitHub Actions Runner

④ 阿里云 ECS

⑤ Docker Container

⑥ PostgreSQL / Redis
```

例如：

```bash
docker build
```

必须明确：

> 到底是在本地、GitHub Runner 还是 ECS 执行？

同理：

```bash
git pull
docker compose up -d
alembic upgrade head
```

都必须明确执行环境。

| 环境 | 是什么 | 负责什么 | 生命周期 |
|------|--------|---------|---------|
| **① 本地电脑** | 你的 Mac | 开发、commit、push | 永久 |
| **② GitHub** | 代码托管平台 | 存储代码、触发 Actions、管理 Secrets | 永久 |
| **③ GitHub Runner** | GitHub 的临时 Ubuntu VM | 执行 CI (lint/test) + CD (SSH 跳板) | 临时（工作流结束即销毁） |
| **④ 阿里云 ECS** | 你的生产服务器 (106.14.206.226) | Nginx、Docker、运行服务 | 永久 |
| **⑤ Docker Container** | ECS 上的隔离进程 | dance-api/dance-postgres/dance-redis | 随 compose 创建/销毁 |
| **⑥ PostgreSQL/Redis** | 容器内的数据库进程 | 持久化数据存储在 Volume 中 | 数据独立于容器生命周期 |

---

# 八、GitHub Actions

重点查看：

```text
.github/workflows/*.yml
```

需要理解：

```yaml
name:
on:
push:
branches:
jobs:
runs-on:
steps:
uses:
run:
with:
env:
secrets:
```

核心关系：

```text
GitHub
 ↓
Workflow
 ↓
Runner
 ↓
执行 CI/CD 脚本
```

必须理解：

> GitHub Actions Runner 和阿里云 ECS 是两台不同的机器。

## CI 流程（基于真实 ci.yml）

### Backend Job

| 步骤 | 命令 | 在哪执行 | 作用 |
|------|------|---------|------|
| Checkout | `actions/checkout@v4` | GitHub Runner | 拉取代码 |
| 安装 uv | `astral-sh/setup-uv@v4` | GitHub Runner | 安装 Python 包管理器 |
| 安装依赖 | `uv sync --frozen` | GitHub Runner | 安装 pyproject.toml 中的依赖 |
| Lint | `uv run ruff check .` | GitHub Runner | 代码风格检查 |
| 类型检查 | `uv run mypy src` | GitHub Runner | 静态类型检查（不阻断） |
| 测试 | `uv run pytest --tb=short -q` | GitHub Runner | 单元测试（不阻断） |

### Frontend Job

| 步骤 | 命令 | 在哪执行 | 作用 |
|------|------|---------|------|
| Checkout | `actions/checkout@v4` | GitHub Runner | 拉取代码 |
| 安装 pnpm | `pnpm/action-setup@v4` | GitHub Runner | 安装 pnpm |
| 安装 Node | `actions/setup-node@v4` | GitHub Runner | 安装 Node.js |
| 安装依赖 | `pnpm install --frozen-lockfile` | GitHub Runner | 安装 workspace 依赖 |
| 构建验证 | `pnpm build` | GitHub Runner | 验证前端能否成功构建 |

**CI 不阻断 CD**：CI 和 CD 是两条独立的工作流，CI 失败不影响 CD 部署。

## CD 流程（基于真实 deploy.yml）

### 部署模式：**模式 A — ECS 拉代码构建**

```
GitHub → Actions → SSH → ECS → git pull → pnpm build → docker build → up
```

### 10 个步骤详解

| 步骤 | 命令 | 作用 |
|------|------|------|
| **0** | `git rev-parse --short HEAD` | 记录 Commit SHA，用于版本追溯 |
| **1** | `git config http.version HTTP/1.1` | 避免 HTTP/2 网络问题 |
| **2** | `git remote set-url origin https://...` | 确保使用 HTTPS 协议 |
| **3** | `git pull origin main` (重试 3 次) | 拉取最新代码 |
| **4** | 创建 `.env.prod` | 确保环境变量文件存在 |
| **5** | `pnpm install` + `pnpm build` → `/var/www/admin/` | 构建并部署前端 |
| **6** | 写入 Nginx 配置 + `reload` | 更新缓存策略，index.html 不缓存 |
| **7** | `docker exec dance-api uv run alembic upgrade head` | 执行数据库迁移 |
| **8** | `docker compose up -d --build` + `docker tag` | 构建新镜像并重启容器，打 Commit SHA 标签 |
| **9** | `curl http://127.0.0.1:8000/health` (最多 30 秒) | 健康检查，验证部署成功 |
| **10** | `docker image prune -f` | 清理无用镜像，释放磁盘 |

---

# 九、SSH 部署原理

典型结构：

```text
GitHub Actions Runner
        │
        │ SSH
        ↓
阿里云 ECS
```

认证：

```text
GitHub Secrets
      ↓
SSH Private Key
      ↓
SSH Authentication
      ↓
ECS ~/.ssh/authorized_keys
```

核心概念：

- Private Key：私钥，不能泄露
- Public Key：公钥
- authorized_keys：服务器允许登录的公钥列表
- Host：服务器地址
- Username：登录用户
- Port：SSH 端口，常见为 22

不能把 SSH 私钥提交到 Git 仓库。

```
GitHub Secrets
    │
    ├── ECS_HOST = "106.14.206.226"
    ├── ECS_USER = "root"
    └── ECS_SSH_KEY = "-----BEGIN OPENSSH PRIVATE KEY-----..."
                              │
                              ↓
GitHub Actions Runner 执行:
    ssh -i <临时私钥文件> root@106.14.206.226
                              │
                              ↓
ECS 检查 ~/.ssh/authorized_keys
    │
    ├── 如果公钥匹配 → 允许登录
    └── 如果不匹配 → 认证失败，部署失败
```

**为什么 GitHub Actions 能登录你的服务器？**

1. 你在服务器生成 SSH 密钥对时，公钥写入了 `~/.ssh/authorized_keys`
2. 你把私钥内容存入 GitHub Secrets
3. GitHub Actions 用这个私钥认证，等同于你本人 SSH 登录

---

# 十、Docker 核心关系

必须区分：

```text
源代码
 ↓
Dockerfile
 ↓
docker build
 ↓
Docker Image
 ↓
docker run / docker compose
 ↓
Docker Container
```

三者不是同一个东西：

```text
源代码 ≠ Image ≠ Container
```

例如：

```text
Git Commit
    ↓
Docker Image
    ↓
dance-api Container
```

修改 Python 代码后，如果生产 Container 中仍然使用旧 Image，就不会自动获得新代码。

```
源代码 (Git Repository)
    ↓
Dockerfile (apps/api/Dockerfile)
    ↓
docker build (在 ECS 上执行)
    ↓
Docker Image (dance-saas-api)
    ↓
docker compose up -d --build
    ↓
Docker Container (dance-api)
    ↓
FastAPI 进程运行
```

**三者不是同一个东西**：

```
源代码 ≠ Docker Image ≠ Docker Container
```

修改 Python 代码后，必须执行 `docker compose up -d --build` 才能更新容器。

---

# 十一、Docker Compose

重点分析真实 Compose 文件中的：

```yaml
services:
image:
build:
ports:
environment:
env_file:
volumes:
depends_on:
networks:
restart:
```

重点理解：

```text
dance-api
dance-postgres
dance-redis
```

三者之间的网络、依赖、端口、Volume 和环境变量关系。

尤其区分：

```bash
git pull
```

与：

```bash
docker compose pull
```

二者完全不同：

- `git pull`：更新 Git 工作目录中的源代码
- `docker compose pull`：从镜像仓库拉取新的 Docker Image

### docker-compose.prod.yml

```yaml
services:
  postgres:
    image: postgres:15-alpine      # 使用官方镜像，不构建
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ..."]

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

  api:
    build:                         # 唯一需要构建的服务
      context: ../../apps/api
      dockerfile: Dockerfile
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    ports:
      - "127.0.0.1:8000:8000"     # 仅绑定本机
```

### `git pull` vs `docker compose pull`

| 命令 | 作用 | 更新什么 |
|------|------|---------|
| `git pull` | 从 GitHub 拉取最新源代码 | Git 工作目录中的代码文件 |
| `docker compose pull` | 从镜像仓库拉取镜像 | Docker Image（如果有 registry 配置） |

当前项目使用 `build` 而非 `image`，所以 `docker compose pull` 不会更新 api 服务。

---

# 十二、如何判断生产代码是否真正更新

常用命令：

```bash
docker ps
```

```bash
docker images
```

```bash
docker inspect dance-api
```

```bash
docker logs dance-api
```

```bash
docker exec -it dance-api ...
```

推荐建立版本对应关系：

```text
Git Commit SHA
      ↓
Docker Image Tag
      ↓
Container
```

例如：

```text
abc1234
   ↓
dance-api:abc1234
   ↓
dance-api Container
```

最终能够回答：

> 当前生产环境运行的是哪个 Git Commit？

### 检查命令

```bash
# 1. 查看容器状态
docker ps

# 2. 查看镜像列表
docker images

# 3. 查看容器详细信息
docker inspect dance-api

# 4. 查看容器日志
docker logs dance-api --tail 50

# 5. 进入容器查看代码
docker exec -it dance-api ls -la /app

# 6. 查看当前运行的镜像标签
docker inspect dance-api --format='{{.Config.Image}}'

# 7. 查看 Commit SHA 标签（如果已部署新版本）
docker images dance-saas-api
```

### 版本追溯

```
Git Commit: abc1234
    ↓
Image Tag: dance-saas-api:abc1234
    ↓
Container: dance-api
```

---

# 十三、数据库不会随着 git push 自动更新

生产数据库：

```text
dance-postgres
      ↓
PostgreSQL 15
      ↓
docker_pgdata
```

必须理解：

```text
Git Repository
```

和：

```text
PostgreSQL Data
```

是两套完全不同的系统。

因此：

```bash
git push
```

本身不会自动：

- 创建数据库表
- 删除数据库表
- 添加字段
- 修改索引
- 修改数据库数据

只有 CI/CD 中明确执行 Migration 时，数据库结构才会随发布更新。

```
Git Repository (代码)
    ≠
PostgreSQL Data (数据)
```

- Git 管理的是**代码文件**
- PostgreSQL 管理的是**数据文件**（在 `pgdata` Volume 中）
- 二者完全独立，互不影响

---

# 十四、Alembic Migration

典型流程：

```text
SQLAlchemy Model
 ↓
Alembic Migration
 ↓
alembic upgrade head
 ↓
PostgreSQL
```

## 1. 生成 Migration

```bash
alembic revision --autogenerate -m "add xxx"
```

作用：

> 根据 SQLAlchemy Model 与当前数据库结构的差异，生成 Migration 文件。

## 2. 执行 Migration

```bash
alembic upgrade head
```

作用：

> 将数据库结构升级到最新 Migration。

关键认知：

```text
代码更新
≠
数据库结构更新
```

生产环境不应该通过：

```text
删除数据库
重新创建数据库
```

来更新结构，而应该通过 Migration。

必须检查实际 CI/CD：

> 当前项目是否自动执行 `alembic upgrade head`？

如果没有，需要设计安全的 Migration 发布流程。

### Alembic Migration 流程

```
SQLAlchemy Model
    ↓
alembic revision --autogenerate -m "add xxx"
    ↓
生成迁移文件 (alembic/versions/xxx.py)
    ↓
提交到 Git
    ↓
部署时执行: alembic upgrade head
    ↓
PostgreSQL 表结构更新
```

**当前 deploy.yml 已包含**：

```bash
docker exec dance-api uv run alembic upgrade head
```

在 `docker compose up --build` **之前**执行，确保数据库结构就绪。

---

# 十五、Docker Volume 与数据库数据

当前：

```text
docker_pgdata
docker_redisdata
```

典型关系：

```text
dance-postgres
      ↓
docker_pgdata
      ↓
ECS 磁盘
```

因此：

```bash
docker compose down
```

通常不会删除 Volume。

但是：

```bash
docker compose down -v
```

可能删除 Compose 管理的 Volume。

尤其危险：

```bash
docker volume rm docker_pgdata
```

因为这可能直接造成 PostgreSQL 数据丢失。

核心原则：

> 更新 `dance-api` 代码时，不应该因为部署代码而删除 PostgreSQL Volume。

生产环境还应该配置数据库备份、恢复验证和备份保留策略。

### 安全操作

| 命令 | 是否删除数据 | 说明 |
|------|-------------|------|
| `docker compose down` | ❌ 不删除 | 只停止容器，Volume 保留 |
| `docker compose down -v` | ⚠️ 删除 | 删除容器 + Volume |
| `docker volume rm pgdata` | 🔴 删除 | 永久删除数据库数据 |

---

# 十六、Nginx

服务器重点查看：

```text
/etc/nginx/nginx.conf
/etc/nginx/sites-enabled/
/etc/nginx/sites-available/
```

同时检查 `/opt/` 项目目录中是否存在额外 Nginx 配置。

常用命令：

```bash
sudo nginx -t
```

作用：

> 检查 Nginx 配置语法。

```bash
sudo nginx -T
```

作用：

> 输出 Nginx 当前实际加载的完整配置，适合判断到底使用了哪些配置文件。

```bash
sudo systemctl reload nginx
```

作用：

> 重新加载配置，通常不需要完全停止 Nginx。

典型配置：

```nginx
server {
    listen 80;
    server_name example.com;
}
```

HTTPS：

```nginx
server {
    listen 443 ssl;
    server_name example.com;
}
```

### 当前服务器（Stage A）

```nginx
server {
    listen 80 default_server;
    server_name _;
    root /var/www/admin;
    index index.html;

    location / {
        # index.html 不缓存
        if ($uri = /index.html) {
            add_header Cache-Control "no-cache, no-store, must-revalidate";
        }
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Nginx 命令区别

| 命令 | 作用 |
|------|------|
| `nginx -t` | 测试配置语法是否正确 |
| `nginx -T` | 显示完整生效配置（包含所有 include） |
| `systemctl reload nginx` | 重新加载配置（不中断现有连接） |
| `systemctl restart nginx` | 重启服务（短暂中断） |

---

# 十七、DNS 与 Nginx 的关系

必须形成以下认知：

```text
DNS
 ↓
"这个域名应该找到哪台服务器？"

Nginx
 ↓
"请求到了这台服务器后，应该交给哪个服务？"
```

例如：

```text
https://api.seplume.com
        ↓
DNS
        ↓
106.14.206.226
        ↓
ECS
        ↓
Nginx :443
        ↓
server_name api.seplume.com
        ↓
127.0.0.1:8000
        ↓
dance-api
        ↓
FastAPI
```

DNS 不负责决定进入哪个 Docker Container。

Nginx 根据：

```text
Host / server_name
```

以及：

```text
location
proxy_pass
```

等配置决定请求如何处理。

### 未来 Stage B 配置

```nginx
# admin.seplume.com - 管理后台
server {
    listen 443 ssl;
    server_name admin.seplume.com;
    root /var/www/admin;
    # ... SSL 配置 ...
}

# api.seplume.com - 纯 API
server {
    listen 443 ssl;
    server_name api.seplume.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        # ... 代理配置 ...
    }
}
```

---

# 十八、当前 IP 前端迁移到域名

当前：

```text
http://106.14.206.226/login
```

未来可能：

```text
https://seplume.com/login
```

或：

```text
https://admin.seplume.com/login
```

迁移路线：

```text
IP 前端
 ↓
DNS 解析
 ↓
Nginx server_name
 ↓
HTTPS
 ↓
前端域名
 ↓
API 域名
 ↓
CORS
 ↓
生产环境变量
 ↓
CI/CD 发布
```

需要检查前端：

```text
VITE_API_BASE_URL
```

如果当前是：

```text
http://106.14.206.226/...
```

最终可能修改为：

```text
https://api.seplume.com
```

但具体值必须以项目实际代码和环境变量为准。

---

# 十九、HTTPS / SSL/TLS

最终目标：

```text
https://seplume.com
```

以及：

```text
https://api.seplume.com
```

典型生产架构：

```text
用户
 ↓
HTTPS
 ↓
Nginx
 ↓
HTTP
 ↓
FastAPI :8000
```

SSL/TLS 通常终止在 Nginx。

原因：

- Nginx 更适合处理 TLS
- FastAPI 不需要直接管理公网证书
- 可以集中管理多个域名
- 可以统一处理 HTTP → HTTPS
- 可以统一配置安全策略

需要理解：

- SSL / TLS
- HTTPS
- Certificate
- Public Key
- Private Key
- CA
- Certificate Chain

### 当前状态

- ❌ 未配置 SSL（只有 HTTP :80）
- 📋 规划中使用 Let's Encrypt + Certbot

### 未来配置

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 申请证书
sudo certbot --nginx -d admin.seplume.com -d api.seplume.com

# 自动续期测试
sudo certbot renew --dry-run
```

### HTTPS 请求流程

```
用户浏览器
    ↓
https://admin.seplume.com
    ↓
DNS → 106.14.206.226
    ↓
Nginx :443 (SSL 终止)
    ↓
解密 HTTPS → 内部 HTTP
    ↓
/var/www/admin/index.html 或 proxy_pass 127.0.0.1:8000
```

---

# 二十、Let's Encrypt + Certbot

Ubuntu 常见安装：

```bash
sudo apt install certbot python3-certbot-nginx
```

申请证书：

```bash
sudo certbot --nginx
```

测试续期：

```bash
sudo certbot renew --dry-run
```

需要理解：

```text
域名
 ↓
DNS
 ↓
ECS
 ↓
Nginx
 ↓
Certbot
 ↓
Let's Encrypt
 ↓
Certificate
 ↓
Nginx
 ↓
HTTPS
```

同时需要确认：

- 证书存放位置
- 私钥存放位置
- Nginx 如何引用
- 证书有效期
- 自动续期机制
- 续期失败如何排查

---

# 二十一、HTTP → HTTPS

典型：

```text
http://seplume.com
        ↓
Nginx :80
        ↓
301 / 308 Redirect
        ↓
https://seplume.com
```

API 同理：

```text
http://api.seplume.com
        ↓
Nginx :80
        ↓
https://api.seplume.com
```

需要理解：

> 安装 SSL 证书并不会让 HTTP 自动变成 HTTPS，必须通过 Nginx 配置 HTTP 到 HTTPS 的重定向。

---

# 二十二、前端与 API 的 CORS

最终可能：

```text
Frontend:
https://admin.seplume.com

API:
https://api.seplume.com
```

虽然属于同一个主域名体系，但仍然是不同 Origin。

需要检查 FastAPI：

```python
from fastapi.middleware.cors import CORSMiddleware
```

生产环境应该明确允许的前端 Origin，例如：

```text
https://admin.seplume.com
https://seplume.com
```

不要为了省事在生产环境长期使用：

```text
allow_origins=["*"]
```

如果项目有 Cookie、Authorization、HTTPS 等认证机制，还需要结合 `allow_credentials` 等配置一起判断。

### 当前（同域）

```
前端: http://106.14.206.226
API:  http://106.14.206.226/api/
```

同域请求，**不需要 CORS 配置**。

### 未来 Stage B（跨域）

```
前端: https://admin.seplume.com
API:  https://api.seplume.com
```

不同 Origin，**需要配置 CORS**。

### FastAPI CORS 配置

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://admin.seplume.com",
        "https://seplume.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

# 二十三、生产环境变量与 Secrets

需要检查：

```text
.env
.env.production
.env.example
Docker Compose
GitHub Secrets
Vite Environment Variables
FastAPI Environment Variables
```

## 前端变量

例如：

```text
VITE_API_BASE_URL
```

注意：

> Vite 的 `VITE_*` 变量最终可能进入前端构建产物，因此不能放真正的秘密。

## 后端变量

例如：

```text
DATABASE_URL
REDIS_URL
JWT_SECRET
```

应该尽量只存在服务器或安全的 Secret 管理系统。

## CI/CD Secrets

例如：

```text
SERVER_HOST
SERVER_USER
SSH_PRIVATE_KEY
```

应该放在 GitHub Secrets 等安全位置。

### 前端变量

```
VITE_API_BASE_URL
```

⚠️ `VITE_*` 变量会被打包到前端产物中，**不能存放秘密**。

### 后端变量

```
DATABASE_URL
REDIS_URL
JWT_SECRET
```

应只存在于服务器 `.env.prod` 或安全 Secret 管理系统。

### CI/CD Secrets

```
ECS_HOST
ECS_USER
ECS_SSH_KEY
```

存放在 GitHub Secrets，**不能提交到 Git**。

---

# 二十四、两种 Docker CI/CD 模式

## 模式 A：服务器构建

```text
GitHub
 ↓
GitHub Actions
 ↓
SSH
 ↓
ECS
 ↓
git pull
 ↓
docker compose build
 ↓
docker compose up -d
```

特点：

- 架构简单
- 不需要镜像仓库
- ECS 需要承担构建工作
- 回滚相对麻烦

适合项目早期。

## 模式 B：CI 构建镜像

```text
GitHub
 ↓
GitHub Actions
 ↓
Docker Build
 ↓
Docker Registry
 ↓
ECS docker pull
 ↓
docker compose up -d
```

特点：

- 构建与生产服务器解耦
- 部署更标准
- 镜像可版本化
- 更容易回滚
- 更适合生产环境和规模化

需要根据当前项目真实配置判断属于哪一种。

---

# 二十五、部署失败排查树

```text
git push
 ↓
GitHub Actions
 ├── 失败
 │    ↓
 │  查看 Actions Logs
 │
 ↓
SSH
 ├── 失败
 │    ↓
 │  检查 Secrets / SSH Key / authorized_keys / Host / Port
 │
 ↓
Docker
 ├── Build Failed
 ├── Image Not Updated
 ├── Container Exit
 └── Port Conflict
 │
 ↓
FastAPI
 ├── 500
 ├── Connection Refused
 └── Database Error
 │
 ↓
PostgreSQL
 ├── relation does not exist
 ├── column does not exist
 └── migration failed
 │
 ↓
Nginx
 ├── 502
 ├── 404
 ├── 403
 └── SSL Error
 │
 ↓
DNS
 ├── 域名无法解析
 ├── DNS 未生效
 └── 解析到错误 IP
```

排查必须遵循：

```text
现象
 ↓
可能原因
 ↓
检查命令
 ↓
正确结果
 ↓
解决方案
```

### 详细排查树

```
git push
   ↓
GitHub Actions
   │
   ├── 🔴 CI 失败 → Actions Logs 查看
   │     ├── ruff check 失败 → 代码风格问题
   │     ├── pytest 失败 → 单元测试问题
   │     └── pnpm build 失败 → 前端构建问题
   │
   ├── 🔴 SSH 连接失败 → 检查 Secrets / authorized_keys
   │
   └── 🔴 CD 失败 → Actions Logs 查看
         ├── git pull 失败 → 网络问题
         ├── pnpm install 失败 → pnpm 未安装
         ├── alembic 失败 → 数据库连接/Migration 问题
         ├── docker build 失败 → Dockerfile/依赖问题
         └── health check 失败 → 容器启动失败
               ↓
         SSH 到 ECS 排查:
               ├── docker ps -a 查看容器状态
               ├── docker logs dance-api 查看日志
               ├── curl http://127.0.0.1:8000/health 测试
               └── nginx -T 检查 Nginx 配置
```

---

# 二十六、手动部署能力

在完全不依赖 GitHub Actions 的情况下，应能够根据真实项目手动执行：

```bash
ssh root@服务器
```

```bash
cd /opt/项目
```

```bash
git pull
```

```bash
docker compose build
```

```bash
docker compose up -d
```

```bash
docker ps
```

```bash
docker logs dance-api
```

```bash
curl http://127.0.0.1:8000/health
```

注意：

> 实际项目中的路径、Compose 文件、构建方式、Migration 命令必须根据真实配置修改，不能盲目照抄。

### 手动部署流程

```bash
# 1. SSH 登录
ssh root@106.14.206.226

# 2. 进入项目目录
cd /opt/dance-saas

# 3. 拉取最新代码
git pull origin main

# 4. 构建前端
pnpm install --frozen-lockfile
cd apps/admin-web && pnpm run build
cp -r dist/* /var/www/admin/
cd /opt/dance-saas

# 5. 执行数据库迁移
docker compose -f infra/docker/docker-compose.prod.yml --env-file .env.prod up -d postgres
docker exec dance-api uv run alembic upgrade head

# 6. 重新构建并启动容器
docker compose -f infra/docker/docker-compose.prod.yml --env-file .env.prod up -d --build

# 7. 打标签
COMMIT_SHA=$(git rev-parse --short HEAD)
docker tag dance-saas-api dance-saas-api:$COMMIT_SHA

# 8. 验证
docker ps
docker logs dance-api --tail 20
curl http://127.0.0.1:8000/health

# 9. 清理
docker image prune -f
```

---

# 二十七、标准生产发布流程

推荐形成以下流程：

```text
本地开发
 ↓
本地测试
 ↓
数据库 Migration 文件检查
 ↓
git status
 ↓
git add
 ↓
git commit
 ↓
git push
 ↓
GitHub Actions
 ↓
CI
 ↓
Test
 ↓
Docker Build
 ↓
CD
 ↓
ECS
 ↓
Database Migration
 ↓
Container Update
 ↓
Health Check
 ↓
Nginx
 ↓
HTTPS
 ↓
API 验证
 ↓
前端验证
```

其中最重要的生产原则：

```text
代码发布
+
数据库 Migration
+
容器更新
+
健康检查
+
回滚能力
```

必须作为一个整体考虑。

---

# 二十八、回滚方案

需要分别理解：

```text
Git 回滚
Docker Image 回滚
Container 回滚
数据库 Migration 回滚
Nginx 配置回滚
前端回滚
```

核心原则：

> 代码回滚 ≠ 数据库回滚。

例如：

```text
v2
 ↓
数据库增加字段
 ↓
v2 部署失败
```

不能简单：

```text
git revert
```

就认为数据库已经恢复。

生产数据库 Migration 必须考虑向前兼容、回滚策略和数据安全。

### 代码回滚

```bash
# 方法 1: GitHub Revert（推荐）
GitHub → Commits → 找到上一个稳定版本 → Revert → 自动触发部署

# 方法 2: 手动回滚
ssh root@106.14.206.226
cd /opt/dance-saas
git log --oneline -10
git reset --hard <commit-hash>
docker compose -f infra/docker/docker-compose.prod.yml --env-file .env.prod up -d --build
```

### 数据库 Migration 回滚

```bash
# 回退一步
docker exec dance-api uv run alembic downgrade -1

# 回退到特定版本
docker exec dance-api uv run alembic downgrade <revision>
```

⚠️ **注意**：不是所有 Migration 都可逆（如 `DROP COLUMN` 会丢数据）。

---

# 二十九、生产安全

重点保护：

```text
SSH Private Key
GitHub Secrets
.env
DATABASE_URL
数据库密码
Redis 密码
JWT Secret
SSL Private Key
Docker Volume
```

原则：

```text
秘密信息
 ↓
不能提交 Git
 ↓
不能暴露前端
 ↓
不能打印到日志
 ↓
使用 Secrets / 环境变量
 ↓
限制权限
```

尤其：

> 前端 `VITE_*` 环境变量不能存放真正的秘密，因为它们可能被打包到浏览器端。

数据库还应该：

- 定期备份
- 定期验证恢复
- 限制公网暴露
- 限制账号权限
- 保留审计和日志

| 敏感信息 | 存储位置 | 禁止行为 |
|---------|---------|---------|
| SSH 私钥 | GitHub Secrets | 提交到 Git |
| `.env.prod` | ECS 本地 | 提交到 Git |
| 数据库密码 | `.env.prod` | 硬编码到代码 |
| JWT Secret | `.env.prod` | 使用默认值 |
| SSL 私钥 | `/etc/letsencrypt/` | 暴露到前端 |

**`.gitignore` 必须包含**：

```
.env*
!.env.example
```

---

# 三十、最终必须掌握的核心问题

## CI/CD

1. CI/CD 是什么？
2. CI 与 CD 有什么区别？
3. GitHub Actions 是什么？
4. Runner 是什么？
5. SSH 在 CI/CD 中解决什么问题？

## Docker

6. Docker Image 与 Container 有什么区别？
7. `dance-api` 如何更新？
8. 为什么代码更新后 Container 不一定自动更新？
9. `docker compose up -d` 做了什么？

## 数据库

10. 为什么 Git push 不会自动更新数据库？
11. Alembic 解决什么问题？
12. `alembic upgrade head` 做什么？
13. Docker Volume 为什么重要？

## Nginx

14. Nginx 在架构中做什么？
15. Nginx 如何把 `api.seplume.com` 转发给 FastAPI？
16. `server_name` 做什么？
17. `listen 80` 与 `listen 443 ssl` 有什么区别？

## DNS

18. `@`、`admin`、`api` 分别是什么意思？
19. DNS 与 Nginx 有什么关系？
20. 为什么多个域名可以指向同一个 IP？

## HTTPS

21. HTTPS 请求发生了什么？
22. SSL/TLS 为什么通常终止在 Nginx？
23. 证书、公钥、私钥、CA、证书链是什么关系？
24. Let's Encrypt + Certbot 如何工作？
25. HTTP 如何跳转 HTTPS？

## 前端

26. 如何从 IP 访问迁移到域名？
27. 前端应该使用 `seplume.com` 还是 `admin.seplume.com`？
28. API Base URL 什么时候修改？
29. CORS 是否需要修改？
30. HTTPS 上线后是否可能出现 Mixed Content？

## 生产

31. 如何判断生产运行的是哪个 Git Commit？
32. 如何判断 Docker Image 是否更新？
33. 如何判断数据库 Migration 是否执行？
34. 如何排查 Nginx 502？
35. 如何排查 HTTPS 失败？
36. 如何回滚？
37. 如何避免数据库数据丢失？
38. 如何实现最小停机或零停机部署？

---

# 三十一、最终知识体系

应该形成以下完整认知：

```text
                    用户
                      │
                      ↓
                   DNS
                      │
                      ↓
              106.14.206.226
                      │
                      ↓
                    Nginx
               ┌──────┴──────┐
               │             │
               ↓             ↓
          Vue Frontend      HTTPS
                             │
                             ↓
                     api.seplume.com
                             │
                             ↓
                       127.0.0.1:8000
                             │
                             ↓
                        Docker
                             │
                         dance-api
                        /         \
                       ↓           ↓
                 PostgreSQL      Redis
                       │           │
                 docker_pgdata  docker_redisdata
```

发布链路：

```text
开发者
 ↓
git push
 ↓
GitHub
 ↓
GitHub Actions
 ↓
CI
 ↓
Test / Build
 ↓
Docker Image
 ↓
SSH / Registry
 ↓
ECS
 ↓
Docker Compose
 ↓
Migration
 ↓
dance-api
 ↓
Health Check
 ↓
Nginx
 ↓
用户
```

最终要把：

```text
CI/CD
+
GitHub Actions
+
SSH
+
Docker
+
Docker Compose
+
PostgreSQL
+
Alembic
+
Docker Volume
+
Nginx
+
DNS
+
SSL/TLS
+
HTTPS
+
Vue
+
FastAPI
```

理解成一个完整的生产系统，而不是互相孤立的知识点。

---

# 三十二、学习和排查时的核心原则

## 原则 1：先看真实配置，再下结论

重点查看：

```text
.github/workflows/
Dockerfile
docker-compose.yml
alembic.ini
alembic/
.env.example
Nginx 配置
```

## 原则 2：明确执行环境

任何命令都必须回答：

```text
本地？
GitHub Runner？
ECS？
Container？
PostgreSQL？
```

## 原则 3：代码、镜像、容器、数据库是不同层

```text
Git Code
   ↓
Docker Image
   ↓
Container
   ↓
Application
   ↓
Database
```

不要把：

```text
代码更新
```

等同于：

```text
数据库更新
```

## 原则 4：DNS、Nginx、HTTPS 分工不同

```text
DNS
→ 找服务器

Nginx
→ 找服务

HTTPS
→ 加密通信
```

## 原则 5：生产数据库优先考虑安全

```text
Migration
+
Backup
+
Rollback
+
Recovery
```

不要通过删除 Volume 或删除数据库来"更新代码"。

---

# 三十三、最终目标

当完整掌握这套体系后，应该能够独立完成：

```text
开发
 ↓
Git
 ↓
CI
 ↓
Docker
 ↓
CD
 ↓
ECS
 ↓
Database Migration
 ↓
Nginx
 ↓
DNS
 ↓
SSL/TLS
 ↓
HTTPS
 ↓
前端
 ↓
FastAPI
```

并能够完成：

**理解 → 手动部署 → 自动部署 → 故障排查 → 回滚 → 优化 → 生产级 CI/CD 设计。**

---

# 三十四、CI/CD 全景图

```
┌──────────────────────────────────┐
│        本地开发电脑 (Mac)         │
│                                  │
│  FastAPI + Vue3 + Git            │
│  开发 → commit → push            │
└──────────────┬───────────────────┘
               │ git push origin main
               ↓
┌──────────────────────────────────┐
│           GitHub                  │
│                                  │
│  Repository + Actions + Secrets  │
│  检测 push → 触发 CI + CD        │
└──────────────┬───────────────────┘
               │
        ┌──────┴──────┐
        ↓             ↓
┌──────────────┐ ┌──────────────────┐
│   CI (ci.yml)│ │ CD (deploy.yml)  │
│              │ │                  │
│  Runner 执行 │ │  Runner SSH →    │
│  lint/test   │ │  ECS 执行部署    │
└──────────────┘ └────────┬─────────┘
                          │ SSH
                          ↓
┌──────────────────────────────────────────────────┐
│                阿里云 ECS                         │
│                                                  │
│  Nginx (:80 → 未来 :443 SSL)                     │
│    │                                             │
│    ├── / → /var/www/admin/ (前端静态文件)         │
│    │                                             │
│    └── /api/ → 127.0.0.1:8000 (反向代理)          │
│                    │                             │
│                    ↓                             │
│            Docker Compose                        │
│                    │                             │
│            ┌───────┼───────┐                     │
│            ↓       ↓       ↓                     │
│       dance-api  dance-  dance-                  │
│       (FastAPI)  postgres redis                  │
│            │       │       │                     │
│            │    pgdata  redisdata                │
│            │    (Volume) (Volume)                │
│            ↓                                     │
│       SQLAlchemy → PostgreSQL / Redis            │
└──────────────────────────────────────────────────┘
```

---

# 三十五、核心认知总结

| 认知 | 说明 |
|------|------|
| **代码 ≠ 镜像 ≠ 容器** | 修改代码后必须 `docker build` 才能更新容器 |
| **Git ≠ 数据库** | `git push` 不会自动更新数据库结构 |
| **DNS ≠ Nginx** | DNS 指向服务器，Nginx 决定服务路由 |
| **HTTP ≠ HTTPS** | 安装证书不会自动跳转，需要 Nginx 配置重定向 |
| **CI ≠ CD** | CI 检查代码质量，CD 部署到生产环境 |
| **Runner ≠ ECS** | Runner 是 GitHub 临时 VM，ECS 是你的生产服务器 |
| **Volume ≠ 容器** | `docker compose down` 不删除 Volume 数据 |