# F1.2 — Release Note

> Feature: JWT Token 主动失效
> 关闭日期：2026-09-26
> 状态：DONE

## Feature

登出后 access_token 立即失效：用户登出后，其旧 access_token 在自然过期前调用任何受保护接口必须返回 401。

## Problem

原系统 logout 仅将 refresh_token 加入 Redis 黑名单，access_token 在最长 120 分钟有效期内仍可正常访问全部 98 处受保护接口。登出不撤销 access_token 违反了项目认证规则（"登出/轮换时将 token 加入黑名单"），存在冒用风险。

## Fix

最小补丁两处收口（复用既有 Redis 黑名单原语，无新组件）：

1. **logout 写入**：从 Authorization 头提取 access_token，按其剩余有效期写入 `blacklist:{token}`（TTL = exp − now）。
2. **认证入口校验**：`get_current_user` 在 JWT 解码成功后、ContextVar 写入前调用 `is_token_blacklisted`，命中抛 401。

refresh_token 黑名单行为（7 天 TTL、一次性使用）完全不变；`get_optional_user` 对黑名单 token 按匿名处理。

## Files Changed

| 文件 | 改动 |
|------|------|
| `apps/api/src/app/core/security.py` | `add_token_to_blacklist` 新增 `ttl_seconds` 参数；新增 `get_token_remaining_ttl` |
| `apps/api/src/app/modules/auth/service.py` | `logout` 新增 access_token 拉黑逻辑 |
| `apps/api/src/app/modules/auth/router.py` | logout 提取 Authorization 头中的 access_token |
| `apps/api/src/app/deps/auth.py` | `get_redis_client` 上移；`get_current_user`/`get_optional_user` 注入 Redis 并校验黑名单 |
| `apps/api/tests/integration/test_auth_api.py` | 新增 6 个黑名单验收用例；修复预存断言（租户头、字段名、手机号生成） |

## Tests

- `tests/integration/test_auth_api.py`：**25/25 通过**（含 F1.2 新增 6 用例）
  - TC-01 登出后 access_token → 401（主验收）
  - TC-03 未登出用户不受影响
  - TC-04 无 refresh_token 登出仍吊销 access
  - TC-08 可选认证端点对黑名单 token 按匿名处理
  - TC-09 重复登出第二次 → 401
  - TC-10 重新登录获得全新可用 token
- `tests/integration/test_rbac_real_redis.py`：6/6 通过（redis 依赖注入不破坏 RBAC）

## Acceptance

| AC | 判定 |
|----|------|
| AC-1 登出后旧 access_token → 401 | ✅ PASS |
| AC-2 黑名单 TTL = 剩余有效期 | ✅ PASS |
| AC-3 认证链路不回归 | ✅ PASS |
| AC-5 变更范围 ⊆ 5 文件白名单 | ✅ PASS |
| AC-6.1 test_auth_api.py 全绿 | ✅ PASS |

Review 结论：**READY_FOR_ACCEPTANCE** → **CLOSE**。

## Known Risks

1. **每认证请求 +1 次 Redis EXISTS**：O(1) 亚毫秒，可接受；高并发下需监控 Redis QPS（属 F7.2 监控）。
2. **`_redis_client` 全局单例跨事件循环**：生产单进程单事件循环无影响；多事件循环测试环境可能 "attached to a different loop"（预存测试架构问题，D-F1.2-2）。
3. **`get_redis_client` 调试输出泄露 Redis URL**（D-F1.2-1）：`print(f"🔗 正在连接 Redis: {settings.REDIS_URL}")` 为预存代码，F1.2 未新增也未清理，建议 F1.3 一并处理。

## Release Notes

- 用户登出后，该设备的 access_token 立即失效，无法再访问任何需要登录的接口。
- refresh_token 刷新流程无变化；登出后 refresh 同样失效，前端既有 401→跳登录链路天然闭环。
- 无 API 契约变更（无新端点、无请求/响应字段变化）；前端无需改动。
- 四端（admin/student/teacher/miniapp）零影响。
