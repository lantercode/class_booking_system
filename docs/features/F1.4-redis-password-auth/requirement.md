# F1.4 — 生产 Redis 密码认证 · Requirement

> Feature ID：F1.4（Epic 1 / Phase 1 / P0）
> 阶段：REQUIREMENT（2026-09-27）

## Goal

生产环境 Redis 必须启用密码认证；后端连接串自动携带密码；开发环境保持无密码以维持现有开发体验。

## Problem

### P1：生产 Redis 无密码（安全）

`infra/docker/docker-compose.prod.yml` L18-28：

- Redis 服务未设置 `command`，默认以无密码模式启动。
- `api` 服务的 `REDIS_URL: redis://redis:6379/0` 同样未携带密码。
- 任何能触达该容器网络/端口（含误暴露到宿主机）的主体均可直接读写 Redis 中的 Token 黑名单、RBAC 权限缓存、限流计数、会话缓存，造成会话劫持与越权。

### P2：配置层缺少密码字段

`apps/api/src/app/core/config.py` L41 仅定义 `REDIS_URL: str = "redis://localhost:6379/0"`，没有 `REDIS_PASSWORD` 字段，运维无法通过环境变量注入密码。

### P3：敏感信息泄露（技术债 D-F1.2-1）

`apps/api/src/app/deps/auth.py:20,25` 使用 `print(f"🔗 正在连接 Redis: {settings.REDIS_URL}")` 打印完整连接串。一旦 URL 携带密码，密码将被明文写入容器日志。

## Scope

1. **T1.4.1**：`infra/docker/docker-compose.prod.yml`
   - redis 服务增加 `command: redis-server --requirepass ${REDIS_PASSWORD}`
   - redis healthcheck 携带密码：`redis-cli -a ${REDIS_PASSWORD} --no-auth-warning ping`
   - api 服务 `REDIS_URL` 改为 `redis://:${REDIS_PASSWORD}@redis:6379/0`
2. **T1.4.2**：`apps/api/src/app/core/config.py` 新增 `REDIS_PASSWORD: str = ""`；`.env.example` 新增同名占位字段
3. **T1.4.3**：创建 `.env.prod.example`（生产模板，含 `REDIS_PASSWORD=change_me_to_strong_password`）；修复 `deps/auth.py` 的 `print` 日志，改为不泄露 URL 的 `logger.debug`

## Out of Scope

- **不修改** `infra/docker/docker-compose.yml`（开发环境保持无密码 Redis）
- **不修改** `apps/api/src/app/deps/auth.py` 中 `get_current_user` / `get_optional_user` 的业务逻辑
- **不修改** `app/core/security.py` 中 `is_token_blacklisted` 等 Redis 读写逻辑（`from_url` 已自动解析 URL 中的密码）
- **不修改** `app/core/rbac/checker.py` 的权限缓存实现
- **不引入** TLS / ACL 用户 / Sentinel / Cluster 等额外 Redis 加固
- **不修改** CI/CD pipeline、Nginx、前端任何端

## User Roles

- 运维/SRE：负责在生产环境设置 `REDIS_PASSWORD` 并重启 compose。
- 后端应用：通过 `REDIS_URL` 自动完成认证，业务代码无感知。
- 攻击者：失去无密码直达 Redis 的路径。

## Business Rules

1. 生产 Redis 必须要求 `AUTH <password>`；未认证客户端收到 `NOAUTH Authentication required`。
2. 密码必须且只能来自环境变量，禁止硬编码在源码、compose 文件或镜像中。
3. `REDIS_PASSWORD` 默认为空字符串，保持开发环境零配置可用。
4. 任何日志、控制台输出不得包含 `REDIS_URL` 完整内容（含密码）。
5. `.env.prod.example` 仅提供占位符，真实密码由运维在部署时注入。

## Dependencies

无前置 Feature；与 F1.2（JWT 黑名单）、F1.3（异常处理器）同属于 Phase 1 安全加固批次。

## Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 生产忘记设置 `REDIS_PASSWORD` 导致 Redis 启动失败或 API 无法连接 | 高 | `.env.prod.example` 显式占位 + 部署检查清单；compose 变量缺失时 Docker 会报错阻止启动 |
| 开发环境误开启密码导致本地启动失败 | 低 | dev compose 不修改；`.env.example` 中 `REDIS_PASSWORD=` 为空 |
| 历史日志/监控告警依赖原有 `print` 输出 | 低 | 统一改为 `logger.debug`，生产默认级别不输出；启动错误仍保留异常类型信息 |
| 密码包含特殊字符导致 URL 解析异常 | 中 | 部署文档提示避免使用 `@`、`:`、`/` 等保留字符，或手动 URL-encode |

## Acceptance Criteria（摘要）

- AC-1：prod compose 启动后，无密码 `redis-cli ping` 返回 `NOAUTH`
- AC-2：正确密码 `redis-cli -a <pwd> ping` 返回 `PONG`
- AC-3：API 启动正常连接 Redis（`REDIS_URL` 含密码）
- AC-4：`deps/auth.py` 不再 print Redis URL，日志不泄露密码
- AC-5：dev compose（`docker-compose.yml`）Redis 行为不受影响
