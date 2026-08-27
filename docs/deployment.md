# 生产环境部署指南 (CI/CD)

> 本文档记录了 `class_booking_system` 从代码提交到自动部署至阿里云 ECS 的完整流程。

## 目录

1. [流水线配置](#1-流水线配置)
2. [密钥管理](#2-密钥管理-github-secrets)
3. [服务器端准备](#3-服务器端准备详细步骤)
4. [验证与回滚](#4-验证与回滚)

---

## 1. 流水线配置

项目包含两条核心流水线，位于 `.github/workflows/` 目录下。

### 1.1 CI (持续集成) — `ci.yml`
**触发条件**：Push 到 `main/dev` 或创建 PR。
**执行任务**：
- **Backend**: 安装依赖 -> Ruff Lint -> Mypy 类型检查 -> Pytest 单元测试。
- **Frontend**: 安装依赖 -> ESLint -> Vite Build。

### 1.2 CD (持续部署) — `deploy.yml`
**触发条件**：Push 到 `main` 分支。
**执行任务**：
- 通过 SSH 登录 ECS。
- `git pull` 拉取最新代码。
- `docker compose up -d --build` 重建并重启服务。
- 清理无用镜像。

---

## 2. 密钥管理 (GitHub Secrets)

敏感信息严禁硬编码，需配置在 GitHub 仓库的 **Settings -> Secrets and variables -> Actions** 中。

| Secret Name | 值说明 | 获取方式 |
| :--- | :--- | :--- |
| `ECS_HOST` | 云服务器公网 IP | 阿里云控制台 -> ECS 实例列表 |
| `ECS_USER` | 登录用户名 | 通常为 `root` |
| `ECS_SSH_KEY` | SSH 私钥内容 | 本地终端执行 `cat ~/.ssh/id_ed25519` 复制全部内容 |

---

## 3. 服务器端准备 (详细步骤)

在首次部署前，需在云服务器上完成环境初始化。

### 3.1 登录与基础软件安装
```bash
# 1. SSH 登录
ssh root@<ECS_HOST>

# 2. 安装 Docker & Git (Ubuntu 22.04)
curl -fsSL https://get.docker.com | bash
apt install -y docker-compose-plugin git

# 3. 验证
docker --version && docker compose version && git --version
```

### 3.2 代码克隆与环境配置
```bash
# 1. 创建目录并克隆代码
mkdir -p /opt/dance-saas && cd /opt/dance-saas
git clone https://github.com/<你的用户名>/class_booking_system.git .

# 2. 配置生产环境变量
cp infra/docker/.env.prod.example .env.prod
vim .env.prod
```

**`.env.prod` 关键配置项**：
- `POSTGRES_PASSWORD`: 使用 `openssl rand -base64 24` 生成强密码。
- `JWT_SECRET`: 使用 `openssl rand -base64 48` 生成随机串。
- `CORS_ORIGINS`: 填写 `http://<ECS_HOST>` 或你的域名。
- `WECHAT_APP_ID/SECRET`: 填入微信小程序后台的真实凭证。

### 3.3 启动服务与数据初始化
```bash
# 1. 启动容器 (Postgres, Redis, API)
docker compose -f infra/docker/docker-compose.prod.yml --env-file .env.prod up -d

# 2. 执行数据库迁移 (Alembic)
docker exec -it dance-api bash -c "cd /app && uv run alembic upgrade head"

# 3. 导入种子数据 (默认租户/角色/管理员)
docker exec -it dance-api bash -c "cd /app && uv run python scripts/seed.py"
```

### 3.4 Nginx 反代配置
```bash
# 1. 安装 Nginx
apt install -y nginx

# 2. 部署配置文件
cp /opt/dance-saas/infra/nginx/nginx.stage-a.conf /etc/nginx/sites-available/dance-saas
ln -sf /etc/nginx/sites-available/dance-saas /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 3. 重启 Nginx
nginx -t && systemctl restart nginx
```

### 3.5 安全组配置
在阿里云控制台开放以下端口：
- **22**: SSH 管理
- **80/443**: Web 访问
- **注意**: 8000 端口**不要**对外开放，仅通过 Nginx 反代访问。

---

## 4. 验证与回滚

### 4.1 验证部署
```bash
# 1. 检查容器状态
docker ps
# 期望: 3 个容器均为 Up (healthy)

# 2. 测试 API 连通性
curl http://127.0.0.1:8000/api/v1/common/health
curl http://<ECS_HOST>/api/v1/common/health

# 3. 测试管理员登录
curl -X POST http://<ECS_HOST>/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone": "13800000001", "password": "Test@123456"}'
```

### 4.2 紧急回滚
如果部署后出现严重 Bug，执行以下操作回滚到上一个版本：
1. **GitHub 操作**: 在仓库 Commits 列表中找到上一个稳定版本，点击 `Revert` 并合并。
2. **自动触发**: 新的 Commit 会自动触发 CD 流水线，将服务器代码回退。
3. **手动回滚 (可选)**:
   ```bash
   cd /opt/dance-saas
   git reset --hard <上一个稳定CommitHash>
   docker compose -f infra/docker/docker-compose.prod.yml --env-file .env.prod up -d --build
   ```