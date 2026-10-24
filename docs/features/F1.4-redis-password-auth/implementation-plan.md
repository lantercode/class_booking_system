# F1.4 — 生产 Redis 密码认证 · 实施方案

> Feature ID：F1.4
> 日期：2026-09-27
> 性质：最小配置补丁（3 修改 + 2 新增），无业务逻辑变更
> 关联文档：[requirement.md](./requirement.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

### 问题 1：生产 Redis 无密码（安全）

- `infra/docker/docker-compose.prod.yml` L18-28：redis 服务缺少 `command`，默认无密码启动。
- L45：api 服务 `REDIS_URL: redis://redis:6379/0`，未携带认证信息。
- 任何可触达 Redis 端口的主体均可直接读写 Token 黑名单、权限缓存等敏感数据。

### 问题 2：配置层缺少密码字段

- `apps/api/src/app/core/config.py` 仅暴露 `REDIS_URL`，未暴露 `REDIS_PASSWORD`，运维无法通过环境变量注入。

### 问题 3：日志泄露连接串（技术债 D-F1.2-1）

- `apps/api/src/app/deps/auth.py:20,25` 使用 `print` 输出完整 `REDIS_URL`。
- 一旦 URL 携带密码，密码将被明文写入容器 stdout / 日志收集系统。

---

## Affected Files

| # | 文件 | 改动内容 |
|---|------|---------|
| 1 | `infra/docker/docker-compose.prod.yml` | redis 加 `command` + healthcheck 带密码；api `REDIS_URL` 带密码 |
| 2 | `apps/api/src/app/core/config.py` | 新增 `REDIS_PASSWORD: str = ""` |
| 3 | `.env.example` | Redis 区块新增 `REDIS_PASSWORD=`（空值，注释提示生产必填） |
| 4 | `.env.prod.example`（新建） | 生产模板，含 `REDIS_PASSWORD=change_me_to_strong_password` 等占位符 |
| 5 | `apps/api/src/app/deps/auth.py` | 移除 `print` 的 URL 输出，改为 `logger.debug` / `logger.error` |

---

## Exact Fix

### 1. docker-compose.prod.yml — Redis 服务加固

```yaml
redis:
  image: redis:7-alpine
  container_name: dance-redis
  restart: unless-stopped
  command: redis-server --requirepass ${REDIS_PASSWORD}
  volumes:
    - redisdata:/data
  healthcheck:
    test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "--no-auth-warning", "ping"]
    interval: 5s
    timeout: 5s
    retries: 5
```

- `command` 在容器启动时强制设置 `requirepass`。
- healthcheck 使用 `-a` 携带密码，`--no-auth-warning` 消除 CLI 警告。
- 若 `REDIS_PASSWORD` 未设置，compose 变量替换为空字符串，Redis 会拒绝空密码或启动失败，从而暴露配置遗漏。

### 2. docker-compose.prod.yml — API 服务连接串

```yaml
environment:
  REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
```

- 采用标准格式 `redis://:<password>@<host>:<port>/<db>`（无用户名，密码前保留冒号）。
- `redis.asyncio.Redis.from_url` 自动解析 `netloc` 中的密码，业务代码零改动。

### 3. config.py — 新增 REDIS_PASSWORD

```python
REDIS_PASSWORD: str = ""
```

- 默认空字符串，开发环境无需修改 `.env` 即可继续使用无密码 Redis。
- 生产环境通过 `.env.prod` 或容器环境变量注入真实密码。

### 4. .env.example — 开发模板提示

```bash
# === Redis ===
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://localhost:6379/0
# 生产环境必须设置强密码；开发环境可留空
REDIS_PASSWORD=
```

### 5. .env.prod.example — 生产模板（新建）

```bash
# === Application ===
APP_NAME=dance-saas
APP_ENV=production
APP_DEBUG=false

# === Database ===
POSTGRES_USER=dance
POSTGRES_PASSWORD=change_me_to_strong_password
POSTGRES_DB=dance_saas
DATABASE_URL=postgresql+asyncpg://dance:change_me_to_strong_password@postgres:5432/dance_saas

# === Redis ===
REDIS_PASSWORD=change_me_to_strong_password

# === JWT ===
JWT_SECRET=change_me_to_strong_jwt_secret
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=120
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# === CORS ===
CORS_ORIGINS=https://admin.yourdomain.com,https://student.yourdomain.com

# === WeChat MiniProgram ===
WECHAT_APP_ID=your_wechat_app_id_here
WECHAT_SECRET=your_wechat_app_secret_here
```

- 仅含占位符，禁止提交真实密码。

### 6. deps/auth.py — 消除 URL 泄露

```python
import logging
logger = logging.getLogger(__name__)

# 修复前
print(f"🔗 正在连接 Redis: {settings.REDIS_URL}")
print(f"✅ Redis 连接成功: {result}")
print(f"❌ Redis 连接失败: {type(e).__name__}: {e}")

# 修复后
logger.debug("正在连接 Redis...")
logger.debug("Redis 连接测试成功")
logger.error(f"Redis 连接失败: {type(e).__name__}: {e}")
```

- 成功日志降为 `debug`，生产默认级别不输出。
- 错误日志保留异常类型与消息，但**不再包含** `REDIS_URL`。

---

## Why This Fix Is Sufficient

1. `requirepass` 是 Redis 官方支持的最小密码认证机制，满足 Phase 1 P0 安全基线。
2. 密码通过环境变量注入，符合 `security/authentication.md` "机密只来自环境变量" 的强制规则。
3. `REDIS_PASSWORD` 默认空字符串，dev compose 不修改，开发体验零影响。
4. `redis.asyncio.Redis.from_url` 自动解析 URL 密码，业务代码（Token 黑名单、RBAC 缓存、限流）无需任何修改。
5. 移除 `print` URL 输出后，密码不再进入 stdout / 容器日志，消除泄露面。

---

## Verification Plan

| AC 编号 | 验证方式 |
|---------|---------|
| AC-1.1 ~ AC-1.3 | yaml 静态检查 + compose 配置审查 |
| AC-2.1 ~ AC-2.3 | 代码审查 + py_compile + URL 格式人工核对 |
| AC-3.1 ~ AC-3.3 | 文件存在性检查 + grep 无真实密码 |
| AC-4.1 ~ AC-4.3 | 代码审查 + py_compile + grep |
| AC-5.1 ~ AC-5.3 | git diff 确认 dev compose 未改 + pytest 回归 |
| AC-6.1 ~ AC-6.3 | minimal-change-guard + py_compile + yaml 语法检查 |

---

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 本地无法启动真实 prod compose 验证 `NOAUTH` | 以 yaml 静态检查 + 命令语义审查代替；生产部署时由运维按 AC-1 验收 |
| U2 | `REDIS_PASSWORD` 含特殊字符（`@`、`:`、`/`）时的 URL 解析 | 部署文档提示避免保留字符或 URL-encode；`redis-py` 支持 percent-encoding |
| U3 | 生产 Redis 持久化数据在首次启用密码后的兼容性 | `requirepass` 仅影响网络认证，不影响 RDB/AOF 文件格式，无需数据迁移 |
