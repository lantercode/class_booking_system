# F1.4 — Acceptance Criteria

> 每条可独立判定 PASS / FAIL。
> 主 AC 为 AC-1；全部 AC 通过方可进入 REVIEW / ACCEPTANCE。

## AC-1 生产 Redis 强制密码认证（主验收标准）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-1.1 | `docker-compose.prod.yml` redis 服务包含 `command: redis-server --requirepass ${REDIS_PASSWORD}` | 代码审查 + yaml 静态检查 |
| AC-1.2 | prod compose 启动后，无密码 `redis-cli ping` 返回 `NOAUTH Authentication required` | 运行时验证（BLOCKED：本地无 prod 环境，以静态检查 + 脚本逻辑审查代替） |
| AC-1.3 | 使用正确密码 `redis-cli -a <pwd> ping` 返回 `PONG` | 运行时验证（同上，以静态检查代替） |

## AC-2 API 自动携带密码连接

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-2.1 | `docker-compose.prod.yml` api 服务 `REDIS_URL` 为 `redis://:${REDIS_PASSWORD}@redis:6379/0` | 代码审查 + yaml 静态检查 |
| AC-2.2 | `config.py` 新增 `REDIS_PASSWORD: str = ""` | py_compile + 代码审查 |
| AC-2.3 | `redis.asyncio.Redis.from_url` 能正确解析含密码的 URL（标准行为） | 代码审查（依赖标准库语义） |

## AC-3 配置模板完备

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-3.1 | `.env.example` 新增 `REDIS_PASSWORD=`（空值）并附生产必填注释 | 代码审查 |
| AC-3.2 | `.env.prod.example` 存在，包含 `APP_ENV=production`、`APP_DEBUG=false`、`REDIS_PASSWORD=change_me_to_strong_password`、`JWT_SECRET` 占位符 | 代码审查 |
| AC-3.3 | 任何文件均未硬编码真实密码 | grep / 代码审查 |

## AC-4 敏感信息不泄露

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-4.1 | `deps/auth.py` 移除 `print(f"...{settings.REDIS_URL}")` 与 `print(f"✅ Redis 连接成功...")` | 代码审查 + py_compile |
| AC-4.2 | `deps/auth.py` 使用 `logger.debug` / `logger.error`，且日志文本不含 URL / 密码 | 代码审查 |
| AC-4.3 | 全仓库新增/修改文件无硬编码密码 | grep `REDIS_PASSWORD` + diff 审查 |

## AC-5 开发环境回归

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-5.1 | `docker-compose.yml`（dev）未修改 | git diff / 代码审查 |
| AC-5.2 | dev 环境下现有 Redis 相关测试（如 `test_auth_api.py` / `test_agent_runtime.py`）通过 | pytest 运行时验证 |
| AC-5.3 | dev 环境 `REDIS_URL` 默认值仍指向 `redis://localhost:6379/0` | 代码审查 |

## AC-6 变更范围（静态）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-6.1 | 实际修改文件 ⊆ {`docker-compose.prod.yml`, `config.py`, `.env.example`, `.env.prod.example`, `deps/auth.py`} | minimal-change-guard |
| AC-6.2 | 修改的 Python 文件通过 `python3 -m py_compile` | STATIC 记录 |
| AC-6.3 | `docker-compose.prod.yml` 通过 yaml 语法检查（`python3 -c "import yaml; yaml.safe_load(...)"`） | STATIC 记录 |

## 判定规则

- 任何 AC-1.x FAIL → Feature 整体 FAIL
- AC-2 ~ AC-6 中出现 FAIL → NEEDS_FIX 回到 DEVELOPMENT
