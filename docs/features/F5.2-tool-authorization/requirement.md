# F5.2 — Tool 授权校验 · Requirement

## 背景

`apps/api/src/app/ai/mcp_server.py` 的写操作 Tool（`create_booking` / `cancel_booking`）在 F5.2 前只检查 `user_id is None`，随后直接调用 BookingService，存在三类缺口：

1. **Authorization 缺失**：任何认证用户（教师、管理员、无角色账号）对 AI 说"帮我预约"都会以自身身份创建预约，违反最小权限。
2. **Input Validation 缺失**：`schedule_id` / `booking_id` 不做范围与类型校验，非法值直接透传到 Service / ORM。
3. **异常被 Tool 吞掉**：两个写 Tool 用 `except Exception as e: return f"预约失败：{str(e)}"` 把原始异常（含内部细节）回显给用户，违反 `ai/mcp.md` 输出安全。

## Goal

写操作 Tool 严格执行四关校验：

```
Authentication → Authorization → Tenant Validation → Input Validation
```

- create_booking / cancel_booking 仅学员角色可调用；
- 非法入参在 Tool 层被友好拒绝；
- 业务异常向 Runtime 传播，由 `_handle_business_error` 映射为不含原文的友好提示。

## Scope

- 修改 `apps/api/src/app/ai/mcp_server.py`：写 Tool 四关校验、移除吞异常 try/except；
- 修改 `apps/api/src/app/ai/agent/runtime.py`：补齐 `tenant_id` 构造参数（AI router 已传但 Runtime 未接收）、`_handle_business_error` 改中文关键词匹配 + 安全兜底；
- 新增测试 `tests/test_mcp_tool_authorization.py`。

## Out of Scope

- 查询类 Tool（query_courses / query_schedules / get_my_bookings / get_my_balance）的改造；
- `ai/tools/` 历史残留清理（F5.4）；
- BookingService 归属校验（已存在，本 Feature 验证其不被绕过）；
- 前端契约（`/api/v1/ai/chat` 请求/响应不变）。
