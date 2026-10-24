# F1.4 — 用户流程（运维视角）

> Feature ID：F1.4
> 关联文档：[requirement.md](./requirement.md) / [acceptance.md](./acceptance.md)

## 1. 主流程：生产部署

```
运维准备 .env.prod
  ├─ REDIS_PASSWORD=<strong_password>
  ├─ JWT_SECRET=<strong_secret>
  └─ POSTGRES_PASSWORD=<strong_password>
  ↓
docker compose -f infra/docker/docker-compose.prod.yml --env-file .env.prod up -d
  ↓
├─ postgres 启动（已有密码）
├─ redis 启动并执行 redis-server --requirepass <password>
│   └─ healthcheck: redis-cli -a <password> ping → PONG
└─ api 启动，环境变量 REDIS_URL=redis://:<password>@redis:6379/0
    └─ get_redis_client() → AsyncRedis.from_url(REDIS_URL) → PING 成功
```

- Redis 容器仅在 compose 内部网络暴露，不映射宿主机端口；密码认证是最后一道防线。
- API 通过 `redis.asyncio.Redis.from_url` 自动解析密码，业务代码零改动。

---

## 2. 异常流程：未设置 REDIS_PASSWORD

```
docker compose --env-file .env.prod up -d
  ↓
.env.prod 中缺少 REDIS_PASSWORD
  ↓
compose 变量替换为空字符串
  ├─ redis-server --requirepass "" → Redis 启动失败或拒绝空密码
  └─ api 的 REDIS_URL 变为 redis://:@redis:6379/0 → 认证失败
  ↓
API 启动失败 / 健康检查失败
```

- **缓解**：`.env.prod.example` 显式要求填写；部署文档/检查清单强制确认；compose 在变量缺失时优先报错而非静默通过。

---

## 3. 异常流程：密码错误

```
REDIS_PASSWORD 在 redis 服务与 api 服务间不一致
  ↓
api 调用 PING → NOAUTH / WRONGPASS
  ↓
get_redis_client() 捕获异常 → logger.error 记录错误类型（不含 URL）
  ↓
AuthException("Redis 连接失败: ...") → HTTP 500 统一信封
```

- 运维可通过 `docker compose logs api` 查看脱敏后的错误信息，按密码不一致方向排查。

---

## 4. 开发流程：本地开发

```
开发者使用根目录 .env（REDIS_PASSWORD= 或缺失）
  ↓
config.py: REDIS_PASSWORD = ""（默认）
  ↓
docker compose -f infra/docker/docker-compose.yml up -d
  ├─ redis 无密码启动
  └─ api 使用 REDIS_URL=redis://redis:6379/0（无密码）
  ↓
开发体验不变
```

- dev compose 文件不修改，本地 Redis 依旧无密码。
- `.env.example` 提供 `REDIS_PASSWORD=` 空值，显式提示"开发可为空，生产必须填"。

---

## 5. 日志输出流程

### 修复前（D-F1.2-1）

```
print("🔗 正在连接 Redis: redis://:password@redis:6379/0")  # 密码泄露到 stdout
print("✅ Redis 连接成功: True")
print("❌ Redis 连接失败: ...")
```

### 修复后

```
logger.debug("正在连接 Redis...")        # 不含 URL，生产级别不输出
logger.debug("Redis 连接测试成功")       # 不含 URL，生产级别不输出
logger.error(f"Redis 连接失败: {type(e).__name__}: {e}")  # 不含 URL，仅错误类型
```

---

## 6. Error 态与空状态

| 场景 | 表现 | 处理 |
|------|------|------|
| 生产未设置 `REDIS_PASSWORD` | Redis 启动失败或 API 认证失败 | 部署检查清单 + compose 变量校验 |
| 密码错误 | API 返回 500，日志提示认证失败 | 核对 `.env.prod` 与 compose 变量 |
| 开发环境密码为空 | Redis 无密码启动，API 正常连接 | 保持现状 |
| `deps/auth.py` 日志 | 不再输出 URL | 仅 logger.debug / logger.error |

---

## 7. Permission / Authentication

- F1.4 不改变 RBAC 权限矩阵，也不改变 Token 黑名单逻辑。
- 它保护的是 **Redis 数据本身**（黑名单、权限缓存、限流、会话）不被未授权读写。
- 认证链路：API 容器 → Redis 容器 → `AUTH <password>` → 正常读写。
