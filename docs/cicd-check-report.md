# CI/CD 配置检查报告

## 检查日期
2026-08-31

---

## 一、发现的问题及修复

### 问题 1：健康检查端点错误（已修复）

**问题描述**：
deploy.yml 中健康检查访问的是 `http://127.0.0.1:8000/health`，但 FastAPI 实际端点是 `/api/v1/common/health`。

**影响**：
健康检查永远失败，部署流程会报错退出。

**修复方案**：
```yaml
# 修复前
curl -sf http://127.0.0.1:8000/health

# 修复后
curl -sf http://127.0.0.1:8000/api/v1/common/health
```

---

### 问题 2：Alembic 迁移在旧容器中执行（已修复）

**问题描述**：
部署流程先执行 `alembic upgrade head`，再 `docker compose up -d --build`。这意味着迁移是在旧代码的容器中执行的，新的 Migration 文件可能不存在。

**影响**：
- 新增的数据库迁移无法执行
- 可能导致数据库 schema 与代码不匹配
- 部署后 API 可能因缺少表/字段而报错

**修复方案**：
```yaml
# 修复前（错误顺序）
docker exec dance-api alembic upgrade head  # 旧容器
docker compose up -d --build                # 新容器

# 修复后（正确顺序）
docker compose build api                    # 先构建新镜像
docker compose up -d api                    # 启动新容器
docker exec dance-api alembic upgrade head  # 新容器执行迁移
```

---

### 问题 3：前端旧文件未清理（已修复）

**问题描述**：
`cp -r dist/* /var/www/admin/` 只会覆盖同名文件，不会删除已不存在的老文件。如果新构建中文件名变化（如 `app.abc123.js` 变为 `app.def456.js`），旧文件会残留。

**影响**：
- 用户可能加载到旧的 JS/CSS 文件
- 可能导致前端报错或显示异常

**修复方案**：
```bash
# 修复前
cp -r dist/* /var/www/admin/

# 修复后
rm -rf /var/www/admin/*        # 先清理旧文件
cp -r dist/* /var/www/admin/   # 再复制新文件
```

---

### 问题 4：CI 测试不阻断流程（已修复）

**问题描述**：
ci.yml 中 pytest 和 mypy 都设置了 `continue-on-error: true`，即使测试失败 CI 也会显示成功。

**影响**：
- 有 bug 的代码也能通过 CI
- 失去 CI 的防护意义

**修复方案**：
```yaml
# 修复前
- name: Test (Pytest)
  run: uv run pytest --tb=short -q
  continue-on-error: true

# 修复后
- name: Test (Pytest)
  run: uv run pytest --tb=short -q
  # 移除 continue-on-error，测试失败则 CI 失败
```

---

### 问题 5：CI 缺少数据库和 Redis 服务（已修复）

**问题描述**：
后端测试需要 PostgreSQL 和 Redis，但 CI 没有启动这些服务。

**影响**：
- 测试无法连接数据库，直接失败
- 即使 `continue-on-error: true`，测试也形同虚设

**修复方案**：
```yaml
# 添加 GitHub Actions Services
services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: test
    ports:
      - 5432:5432
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
  redis:
    image: redis:7-alpine
    ports:
      - 6379:6379
    options: >-
      --health-cmd "redis-cli ping"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

---

### 问题 6：Nginx 配置被覆盖（已修复）

**问题描述**：
deploy.yml 中硬编码了一个简化的 Nginx 配置（只监听 80 端口），会覆盖掉 `infra/nginx/nginx.conf` 中更完善的配置（HTTPS、多域名、SSL 等）。

**影响**：
- 每次部署都会丢失 HTTPS 配置
- 多域名支持失效
- SSL 证书配置丢失

**修复方案**：
```bash
# 修复前（硬编码简化配置）
NGINX_CONF='server { listen 80 ... }'
echo "$NGINX_CONF" > /etc/nginx/sites-available/dance-saas

# 修复后（使用项目标准配置）
cp infra/nginx/nginx.conf /etc/nginx/sites-available/dance-saas
# 从 .env.prod 读取域名并替换占位符
sed -i "s/admin\.yourdomain\.com/$ADMIN_DOMAIN/g" /etc/nginx/sites-available/dance-saas
sed -i "s/api\.yourdomain\.com/$API_DOMAIN/g" /etc/nginx/sites-available/dance-saas
```

---

### 问题 7：镜像标签命令优化（已修复）

**问题描述**：
`docker tag dance-saas-api dance-saas-api:$COMMIT_SHA` 中的镜像名可能不正确，Docker Compose 默认镜像名格式是 `<项目目录>-<服务名>`。

**修复方案**：
```bash
# 修复后（动态获取实际镜像名）
API_IMAGE=$(docker compose -f infra/docker/docker-compose.prod.yml --env-file .env.prod config | grep -A1 'api:' | grep 'image:' | awk '{print $2}' || echo "")
if [ -z "$API_IMAGE" ]; then
  API_IMAGE="docker-dance-saas-api"
fi
docker tag "$API_IMAGE" "$API_IMAGE:$COMMIT_SHA"
```

---

## 二、部署流程验证

### 修复后的完整部署流程

```
1. 代码推送到 main 分支
       |
2. CI 工作流触发
   ├── 后端：Lint + Type Check + Test（需要 PostgreSQL + Redis）
   └── 前端：Install + Build
       |
3. CI 通过后，Deploy 工作流触发
       |
4. SSH 到阿里云 ECS
       |
5. git pull 最新代码
       |
6. 构建前端
   ├── rm -rf /var/www/admin/*        ← 清理旧文件
   ├── pnpm install --frozen-lockfile
   ├── cd apps/admin-web && pnpm run build
   └── cp -r dist/* /var/www/admin/
       |
7. 配置 Nginx
   ├── cp infra/nginx/nginx.conf → /etc/nginx/sites-available/
   ├── 替换域名占位符
   └── nginx -t && systemctl reload nginx
       |
8. 构建并启动新容器
   ├── docker compose build api       ← 先构建新镜像
   ├── docker compose up -d api       ← 启动新容器
   └── docker exec dance-api alembic upgrade head  ← 新容器执行迁移
       |
9. 健康检查
   ├── curl http://127.0.0.1:8000/api/v1/common/health
   └── 验证返回状态
       |
10. 镜像标签 + 清理
    ├── docker tag <image> <image>:<commit-sha>
    └── docker image prune -f
```

---

## 三、前端获取最新代码验证

### 缓存控制策略

| 资源类型 | 缓存策略 | 说明 |
|---------|---------|------|
| `index.html` | `no-cache, no-store, must-revalidate` | 每次请求都向服务器验证，确保获取最新版本 |
| `.js/.css`（含哈希文件名） | `expires 1y; immutable` | 长期缓存，文件名变化时自动更新 |
| 图片/字体 | `expires 1y; immutable` | 长期缓存 |

### 用户访问流程

```
用户访问 https://admin.yourdomain.com
    |
Nginx 返回 index.html（不缓存）
    |
浏览器解析 HTML，加载 JS/CSS（文件名含哈希）
    |
如果 JS/CSS 文件名变化 → 浏览器重新下载
如果 JS/CSS 文件名未变 → 使用缓存
```

### 验证方法

部署后，用户可以通过以下方式验证：

1. **硬刷新浏览器**：`Ctrl+Shift+R`（Windows）或 `Cmd+Shift+R`（Mac）
2. **检查 Network 面板**：查看 `index.html` 的响应头是否包含 `Cache-Control: no-cache`
3. **检查 JS/CSS 文件名**：确认文件名包含新的哈希值

---

## 四、还需要手动配置的内容

### 1. .env.prod 文件（在 ECS 上）

```bash
# 数据库
POSTGRES_USER=dance
POSTGRES_PASSWORD=your_password
POSTGRES_DB=dance_saas

# JWT
JWT_SECRET=your_jwt_secret

# 域名
ADMIN_DOMAIN=admin.yourdomain.com
API_DOMAIN=api.yourdomain.com

# CORS
CORS_ORIGINS=https://admin.yourdomain.com,https://api.yourdomain.com

# 微信
WECHAT_APP_ID=your_app_id
WECHAT_SECRET=your_secret
```

### 2. SSL 证书（首次部署后）

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d admin.yourdomain.com -d api.yourdomain.com
```

### 3. GitHub Secrets

在 GitHub 仓库 Settings → Secrets and variables → Actions 中配置：

| Secret | 说明 |
|--------|------|
| `ECS_HOST` | 阿里云 ECS 公网 IP |
| `ECS_USER` | SSH 用户名 |
| `ECS_SSH_KEY` | SSH 私钥 |

---

## 五、总结

| 类别 | 修复前 | 修复后 |
|------|--------|--------|
| 健康检查 | 端点错误，永远失败 | 使用正确端点 `/api/v1/common/health` |
| 数据库迁移 | 在旧容器中执行 | 先构建新容器，再执行迁移 |
| 前端部署 | 旧文件残留 | 先清理再部署 |
| CI 测试 | 不阻断流程 | 测试失败则 CI 失败 |
| CI 服务 | 缺少 PostgreSQL + Redis | 使用 GitHub Actions Services |
| Nginx 配置 | 覆盖完善配置 | 使用项目标准配置 + 域名替换 |
| 镜像标签 | 镜像名可能错误 | 动态获取实际镜像名 |

**修复后，提交代码到 main 分支即可自动完成：**
1. CI 检查（Lint + Test）
2. 构建前端并部署到 `/var/www/admin`
3. 构建后端 Docker 镜像并启动
4. 执行数据库迁移
5. 健康检查验证
6. 用户访问前端即可获取最新代码