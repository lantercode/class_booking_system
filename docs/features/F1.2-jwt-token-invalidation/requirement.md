# F1.2 — JWT Token 主动失效 · Requirement

> Feature ID：F1.2（Epic 1 / Phase 1 / P0）
> 阶段：REQUIREMENT（2026-09-26）
> 状态：READY → 需求已确认，待 DEVELOPMENT
> 前置：Pre-Change Guard 已通过（2026-09-26，5 个白名单文件全部 CLEAN）

---

## Goal

登出后 access_token 立即失效：用户登出后，其旧 access_token 在自然过期前调用任何受保护接口必须返回 401。

## Problem

当前系统是无状态 JWT + 双 Token：

- access_token 有效期 120 分钟（`core/config.py:44`），签发后服务端无任何撤销手段
- logout 仅将 **refresh_token** 加入 Redis 黑名单（`modules/auth/service.py:286`），access_token 仍可在最长 2 小时内正常访问全部受保护接口（共 98 处 `Depends(get_current_user)`，覆盖 14 个 router 文件）
- 认证依赖 `get_current_user`（`app/deps/auth.py:11-31`）解码 JWT 后**没有任何黑名单校验**
- 风险：用户登出（尤其在共用设备/ token 泄露场景）后，旧 token 仍可被冒用访问数据，违反 `.trae/rules/security/authentication.md`（"登出/轮换时将 jti 加入 Redis 黑名单"）

## User Story

- 作为用户，我在一台设备上登出后，该设备残留的旧 access_token 应立即无法访问任何需要登录的接口。
- 作为安全负责人，我希望撤销机制不依赖 JWT 自然过期，且黑名单记录不永久堆积。

## Scope（Expected Scope，已冻结）

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/core/security.py` | 黑名单写入函数支持按"token 剩余有效期"设置 TTL（保持 refresh 现有 7 天默认行为不变）；新增从 token 解析剩余 TTL 的小工具函数 |
| 2 | `apps/api/src/app/modules/auth/service.py` | `logout` 在拉黑 refresh_token 的同时拉黑 access_token（TTL=剩余有效期） |
| 3 | `apps/api/src/app/modules/auth/router.py` | logout 端点从 `Authorization` 头提取当前 access_token 传入 service；请求体契约不变（refresh_token 仍为可选字段） |
| 4 | `apps/api/src/app/deps/auth.py` | `get_current_user` 解码成功后校验黑名单，命中抛 401；`get_optional_user` 将黑名单 token 视为匿名（返回 None） |
| 5 | `apps/api/tests/integration/test_auth_api.py` | 新增登出黑名单集成测试（真实 Redis，沿用现有 live_server 夹具） |

## Out of Scope

- 不改 JWT 签发结构、密钥、过期时长、payload 字段
- 不改 refresh_token 轮换逻辑与一次性使用语义（`service.py:290+`）
- 不改前端任何代码（前端 401→refresh→401→跳登录的拦截器已存在，登出后 refresh 也会因 refresh_token 被拉黑而 401，链路天然闭环）
- 不改 OpenAPI 请求/响应契约：不新增端点、不改 logout 请求体与响应体
- 不引入 token 黑名单数据库表、不做设备维度/会话列表/踢人下线
- 不重构 `deps/auth.py` 的全局 `_redis_client` 单例（既有技术债）
- 不处理 `PERMISSION_CHECK_BYPASS`（F1.1）、通用 Exception handler（F1.3）
- 不动工作区 63 项预存改动

## User Roles

- 学员 / 教师 / 管理员等所有持有 access_token 的角色：行为一致，无角色差异。
- MCP Tool 调用链：身份由 AgentRuntime 注入，不经 HTTP 认证依赖，**不受影响**；但 `POST /api/v1/ai/chat` 经 `get_agent_runtime → Depends(get_current_user)`（`modules/ai/router.py:48-56`），黑名单 token 访问该端点同样 401（符合预期）。

## Business Rules

1. logout 必须同时拉黑 access_token 与 refresh_token（若请求体提供了 refresh_token，保持其可选语义）。
2. access_token 黑名单 TTL = 该 token `exp` − 当前时间（秒）；解析不出 exp 或已过期的 token 无需写入（本就无法通过解码）。
3. Redis key 沿用现有格式与开关：`blacklist:{token}`、`ENABLE_TOKEN_BLACKLIST=True` 时生效；开关关闭时行为与现状完全一致（函数早退）。
4. 黑名单校验在 JWT 解码通过之后、`set_tenant_id/set_user_id/set_role_id` 写入 ContextVar 之前执行——被撤销的身份不得建立请求上下文。
5. `get_optional_user`（仅 `modules/teacher/router.py:30` 使用）遇到黑名单 token 返回 None（匿名语义），不抛异常。
6. 失败语义：Redis 不可用时认证采取 fail-closed（不允许在无法确认撤销状态时放行）；`get_redis_client` 连接失败现有行为即抛 AuthException，本 Feature 不新增吞异常逻辑。
7. 黑名单是幂等的：重复登出、同一 token 多次写入不报错（SETEX 语义覆盖）。

## Dependencies

- Redis 7（生产强制可达，见 authentication.md）；黑名单原语 `add_token_to_blacklist` / `is_token_blacklisted` 已存在（`security.py:113-127`），本 Feature 复用不新建
- 无前置 Feature 依赖；不依赖 F1.1
- 测试依赖：`tests/conftest.py` 已有真实 Redis 夹具（`ensure_redis_available`，L44-55）与 live_server + AsyncClient 夹具（L312-313）

## API Contract

**无契约变更。** logout 仍为 `POST /api/v1/auth/logout`，access_token 从既有 `Authorization: Bearer` 头取得（该头当前已为必需——端点本身依赖 `get_current_user`），请求体 `{"refresh_token": "..."}` 仍可选；响应仍为统一信封 `{code:0,msg:"登出成功"}`。故不单独创建 api-contract.md。

## Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 98 处认证依赖每个请求多一次 Redis EXISTS，增加延迟与 Redis 负载 | 低 | EXISTS 为 O(1)；Redis 同机房亚毫秒；必要时后续可改 jti 短 key（不在本 Feature） |
| Redis 故障导致全站认证 fail-closed | 中 | 与既有设计一致（生产 Redis 已被黑名单/限流/会话强依赖，lifespan 即要求可达）；在 architecture 中明确故障语义 |
| TTL 计算边界（token 恰在登出瞬间过期、时钟偏移） | 低 | 以 exp 解析结果为准；decode 已有 10s leeway；剩余 TTL ≤0 时跳过写入 |
| access/refresh 黑名单 key 冲突 | 无 | key 含完整 token 字符串，两类 token 不可能相同；且 refresh payload 含 `type:"refresh"` |
| 回归 refresh 流程 | 低 | refresh 端点不依赖 get_current_user（router.py:112-116），只认请求体 refresh_token；加回归测试 |
| 预存工作区改动污染提交 | 低 | Pre-Change Guard 已冻结哈希；STATIC 阶段 verify-scope.sh 5 文件白名单 |

## 验收标准（摘要，详见 acceptance.md）

登出 → 旧 access_token 调用任一受保护接口 = 401；未登录 = 401；登出后 refresh = 401；未登出 token 正常 200；可选认证端点对黑名单 token 按匿名处理。
