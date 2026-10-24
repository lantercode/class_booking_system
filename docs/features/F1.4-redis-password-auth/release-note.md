# F1.4 — Release Note

> Feature: 生产 Redis 密码认证
> 关闭日期：2026-09-27（待生产部署窗口完成 AC-1.2/1.3 人工验收后正式 Close）
> 状态：READY_FOR_ACCEPTANCE

## Feature

生产环境 Redis 强制密码认证；后端连接串自动携带密码；消除 Redis URL 日志泄露（技术债 D-F1.2-1）。

## Problem

1. **生产 Redis 无密码**：`docker-compose.prod.yml` redis 服务无 `command`，api 的 `REDIS_URL` 无密码，Token 黑名单 / RBAC 缓存 / 限流数据可被未认证读写。
2. **配置层无密码字段**：`config.py` 仅有 `REDIS_URL`，运维无法注入密码。
3. **URL 日志泄露**：`deps/auth.py` `print` 完整 `REDIS_URL`，一旦携带密码即明文入库日志系统。

## Fix

最小补丁，4 修改 + 1 新建：

1. **prod compose 加固**：redis 以 `redis-server --requirepass ${REDIS_PASSWORD}` 启动；healthcheck 携带密码；api `REDIS_URL` 改为 `redis://:${REDIS_PASSWORD}@redis:6379/0`。
2. **配置字段**：`config.py` 新增 `REDIS_PASSWORD: str = ""`（默认空，dev 零影响）。
3. **模板**：`.env.example` 新增空值占位 + 注释；新建 `.env.prod.example` 生产模板（全占位符）。
4. **日志脱敏**：`deps/auth.py` 3 处 `print` 改为 `logger.debug` / `logger.error`，不再输出 URL；附带移除仅为 print 服务的重复 `ping()`。

## Files Changed

| 文件 | 改动 |
|------|------|
| `infra/docker/docker-compose.prod.yml` | redis `command` + healthcheck 带密码；api `REDIS_URL` 带密码 |
| `apps/api/src/app/core/config.py` | 新增 `REDIS_PASSWORD: str = ""` |
| `.env.example` | 新增 `REDIS_PASSWORD=` 空值占位 |
| `.env.prod.example` | 新建生产模板 |
| `apps/api/src/app/deps/auth.py` | print → logger，URL 不再输出 |

## Tests

- `test_auth_api.py` 集成回归：**15/15 通过**（register/login/logout/黑名单，实际读写 dev 无密码 Redis）
- `test_exception_handlers.py` F1.3 回归：**7/7 通过**
- `test_agent_runtime.py` AI 回归：**5/5 通过**
- `Settings` 直调：`REDIS_PASSWORD` 默认空、env 注入生效、dev `REDIS_URL` 默认值不变
- `redis-py from_url` 直调：含密码 URL 正确解析（password/host/port/db）
- `docker compose config` 渲染：`command` / healthcheck / `REDIS_URL` 三处插值正确
- `py_compile` × 2、`yaml.safe_load` × 2：全部通过

## Acceptance

| AC | 判定 |
|----|------|
| AC-1 prod Redis 强制认证 | PASS（运行时 NOAUTH/PONG 条款留部署窗口人工验收） |
| AC-2 API 携带密码连接 | PASS |
| AC-3 模板完备无硬编码 | PASS |
| AC-4 日志不泄露 | PASS |
| AC-5 dev 回归 | PASS |
| AC-6 变更范围 ⊆ 白名单 | PASS |

Review 结论：**READY_FOR_ACCEPTANCE**（附生产人工验收条款）。

## Known Risks

1. **部署遗漏密码**：compose 对缺失变量输出 warning 且 Redis 认证失败可导致 api 不健康，部署窗口可立即发现，不会静默裸奔。
2. **密码特殊字符**：避免 `@`、`:`、`/` 等 URL 保留字符，或 URL-encode。
3. **存量 print**：`main.py`、`modules/auth/service.py` 存在不含敏感信息的 print，登记为后续日志规范化候选。

## Release Notes

- 生产 Redis 现在要求 `AUTH` 密码认证；无密码客户端将收到 `NOAUTH Authentication required`。
- 后端通过 `REDIS_URL` 自动携带密码，业务代码（Token 黑名单、权限缓存、限流）零改动。
- 修复技术债 D-F1.2-1：Redis 连接日志不再输出 URL，密码不进入容器日志。
- 开发环境（dev compose + 本地 `.env`）完全不受影响，无密码 Redis 体验不变。
- **部署动作**：运维需在 `.env.prod` 设置 `REDIS_PASSWORD=<strong_password>`（建议 `openssl rand -base64 32`），滚动重启后在容器内执行 `redis-cli ping`（应 NOAUTH）与 `redis-cli -a <pwd> ping`（应 PONG）完成人工验收。
