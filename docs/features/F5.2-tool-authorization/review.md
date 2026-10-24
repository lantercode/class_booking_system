# F5.2 — Review

## Scope Review

- 改动严格限定在 AI 写操作链路：mcp_server.py 两个 Tool + runtime.py 错误处理与构造参数 + 1 个新测试文件；
- 查询类 Tool、BookingService、Repository、前端、OpenAPI 均未触碰；
- 未引入新依赖、新表、新配置。

## Architecture Review（对照 .trae/rules/ai）

| 规则 | 结论 |
|------|------|
| 四关顺序 Authentication → Authorization → Tenant → Input | ✅ 已按序实现（实施中一度为 fail-fast 把 Input 前置，已纠正） |
| Tool 只能调 Service | ✅ 写 Tool 仅调 BookingService；角色查询走 RBAC 核心基础设施 |
| 禁止 Tool 直连 Repository / 裸 SQL / Redis | ✅ grep 无匹配 |
| 身份来自 Runtime 注入、不信任 LLM | ✅ user_id 仅来自 get_current_user 链路 |
| 业务异常转用户可理解文本、不抛 traceback | ✅ Tool 传播 + Runtime 友好映射，兜底不含原文 |
| 单一 Tool 注册点 FastMCP | ✅ 未在 ai/tools/ 新增内容 |
| 写操作幂等 | ✅ 复用 Service 既有行锁/状态重检，Tool 不另造事务 |
| 核心业务规则只在 Service | ✅ 容量/扣次/归属仍在 BookingService，Tool 未复制 |

## Code Review

- `_validate_id` 显式排除 `bool`（Python 中 `isinstance(True, int)` 为 True），正确；
- `_require_student_role` 对空集合默认拒绝，满足最小权限；
- reason 校验同时覆盖类型与长度；
- 错误文案经过 not-in 断言验证，不包含原始异常子串；
- 无 print、无 URL/Token/堆栈输出。

## Regression Review

- 新增 18/18；F5.3 映射 10/10；rbac + booking_ownership 27/27；
- 2 个预存失败为 F5.1 脚本测试的 DB/mock 依赖，已在 runtime-test-report 中用"改动前即失败"的证据排除。

## Acceptance Review

AC-1～AC-11、AC-13、AC-14 均有自动化或静态证据；AC-12 回归除 2 个预存数据依赖用例外通过。

## Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 角色查询增加一次 DB 往返（每次写操作） | 低 | 单次主键 JOIN；写操作非高频 |
| Tool 签名无 tenant_id，依赖请求 ContextVar | 中 | HTTP /ai/chat 链路 middleware 已设置；stdio 独立会话显式传 tenant 留作后续议题 |
| 管理员代学员预约的业务诉求被 403 拒绝 | 低 | AI 助手定位为学员自助；代客操作走管理后台 HTTP 端点 |

## New Tech Debt

- D-F5.2-1：查询类 Tool（get_my_bookings/get_my_balance）仍直写 select/透传 user_id，应收口为 Service 调用；
- D-F5.2-2：test_agent_runtime.py 中两个 F5.1 脚本式用例依赖 dev DB 数据，需改造为自造数据用例；
- D-F5.2-3：stdio MCP 独立进程下的显式 tenant 传递机制评估。

## Recommendation

**READY_FOR_ACCEPTANCE**
