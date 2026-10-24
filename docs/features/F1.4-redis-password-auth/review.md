# F1.4 — 生产 Redis 密码认证 · Feature Review

> Feature ID：F1.4
> 评审日期：2026-09-27
> 评审性质：主 Agent 对照 AC 复核（简单单域后端/配置修复）
> 评审输入：requirement.md / user-flow.md / acceptance.md / implementation-plan.md / implementation-report.md / static-verification.md / runtime-test-report.md + 独立 git diff 与源码核查

---

## Scope Review

**结论：严格遵守 F1.4 Scope。**

| 文件 | diff 实证 | 判定 |
|------|----------|------|
| `infra/docker/docker-compose.prod.yml` | 仅 3 处增量：redis `command`、healthcheck `test`、api `REDIS_URL` | 与 plan 一致 |
| `apps/api/src/app/core/config.py` | 仅新增注释 + `REDIS_PASSWORD: str = ""` | 与 plan 一致 |
| `.env.example` | 仅新增 `REDIS_PASSWORD=` 两行 | 与 plan 一致 |
| `.env.prod.example` | 新建，全占位符 | 与 plan 一致 |
| `apps/api/src/app/deps/auth.py` | 3 处 print → logger；移除重复 ping；新增 import logging + logger | 与 plan 一致 |

- 未修改 dev compose、Service / Router / 业务代码、前端。
- 未触碰工作区预存改动（F1.1/F1.2/F1.3 等的未提交修改在 diff 中可区分，本 Feature 仅为增量）。
- 唯一的顺手清理（重复 `ping()`）与被删除的 print 强耦合，属合理最小附带改动，已如实记录。

## Architecture Review

**结论：符合架构规则，无违规。**

- 分层：仅修改基础设施编排与配置层，不触碰 Router → Service → Repository 业务链路，符合 `architecture/layering.md`。
- 机密管理：密码只来自环境变量（`${REDIS_PASSWORD}` 插值 + `.env.prod` 被 gitignore），无硬编码，符合 `security/authentication.md`。
- Redis 连接点唯一性：全后端仅 `deps/auth.py:26` 一处 `from_url(REDIS_URL)`，黑名单 / RBAC 缓存 / 限流均经依赖注入复用 → URL 带密码即全链路带密码，无绕过。
- 日志安全：满足"禁止在日志中暴露 Token、密钥"规则；error 日志保留异常类型但剔除 URL。
- 契约：无 API 变更，四端无影响面。

## Code Review

**结论：最小修复，无隐藏行为变化。**

1. `command: redis-server --requirepass ${REDIS_PASSWORD}`：Redis 7 官方支持的认证方式；变量缺失时 compose 明确 warning，且空密码导致认证失败可在部署窗口立即暴露。
2. healthcheck 加 `-a ${REDIS_PASSWORD} --no-auth-warning`：保证 `depends_on: service_healthy` 在启用密码后仍能正确门控 api 启动顺序。
3. `REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0`：标准 `redis://:password@host` 格式（无用户名段），`redis-py` 解析行为经直调验证。
4. `REDIS_PASSWORD: str = ""`：默认空兼容 dev；字段存在使运维可通过 `.env.prod` 显式注入。
5. `deps/auth.py`：logger 模式与项目其他模块一致；生产默认级别下 debug 不输出；error 不泄露 URL。

## Regression Review

**结论：回归风险低，已有实证。**

- dev 认证链路：`test_auth_api.py` 15/15 通过（含 logout → Redis 黑名单读写）。
- F1.3 同文件回归：`test_exception_handlers.py` 7/7 通过（`config.py` 仅增字段，不改既有字段语义）。
- AI 链路：`test_agent_runtime.py` 5/5 通过。
- dev compose：未修改，本地无密码 Redis 体验不变。
- `get_redis_client` 行为：延迟初始化、单例缓存、ImportError / 连接失败的 `AuthException` 语义全部保留。

## Acceptance Review

| AC | 判定 | 依据 |
|----|------|------|
| AC-1 prod Redis 强制认证 | **PASS*** | 渲染验证 + 指令语义审查；*AC-1.2/1.3 留生产窗口人工验收 |
| AC-2 API 携带密码连接 | **PASS** | diff + 渲染 + `from_url` 直调 |
| AC-3 模板完备 | **PASS** | 文件审查 + grep |
| AC-4 不泄露 | **PASS** | grep + 代码审查 |
| AC-5 dev 回归 | **PASS** | 32/32 pytest |
| AC-6 变更范围 | **PASS** | minimal-change-guard + py_compile + yaml |

## Risks

| # | 风险 | 等级 | 处置建议 |
|---|------|------|---------|
| R1 | 生产部署忘记设置 `REDIS_PASSWORD` | 高 | compose warning + `.env.prod.example` 占位 + 部署检查清单；启动失败可立即发现，不会静默裸奔 |
| R2 | 密码含 URL 保留字符导致解析异常 | 中 | 部署文档提示字母数字或 URL-encode |
| R3 | main.py / auth/service.py 存在无敏感信息的 print | 低 | 非泄露面，登记为后续日志规范化技术债候选，不在本 Feature 修 |
| R4 | 生产 Redis 启用密码前的历史数据卷（redisdata） | 低 | `requirepass` 仅影响网络认证，不影响 RDB/AOF 格式，无需迁移 |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 真实 prod 环境 NOAUTH/PONG 行为 | 本地无法复现；渲染证据充分，部署窗口按 AC-1.2/1.3 人工验收 |
| U2 | 生产 Redis 是否计划额外开启 TLS/ACL | 超出 F1.4 Scope，如有需求另立 Feature |

## Recommendation

1. **代码层面**：F1.4 修复正确、最小、完整，无需返工。
2. **验收层面**：本地可验证 AC 全部通过；AC-1.2/AC-1.3 标记为部署窗口人工验收项。
3. **部署层面**：运维需在 `.env.prod` 设置强密码（建议 `openssl rand -base64 32`），并计划滚动重启窗口；首次启动后执行 AC-1.2/1.3 验证。

**最终结论：READY_FOR_ACCEPTANCE（附生产人工验收条款 AC-1.2/AC-1.3）**
