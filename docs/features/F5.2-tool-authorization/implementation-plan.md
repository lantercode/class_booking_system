# F5.2 — Implementation Plan

## Root Cause

`mcp_server.py` 的写操作 Tool 只做了"user_id 是否存在"的检查，缺少四关中的 Authorization 与 Input Validation；并用 `except Exception: return f"...失败：{e}"` 吞异常回显原文。同时排查发现两个连带问题：

- `AgentRuntime.__init__` 不接收 `tenant_id`，但 AI router（`modules/ai/router.py`）与测试均已传入 → TypeError；
- `runtime._handle_business_error` 仍是英文错误码映射（`SCHEDULE_FULL` 匹配中文消息恒不命中）+ 兜底回显 `{error}`，F5.3 的约束在当前代码上未生效。授权异常必须依赖它做友好映射，因此本 Feature 一并修复。

## Affected Files

| 文件 | 改动 |
|------|------|
| `apps/api/src/app/ai/mcp_server.py` | 新增 `_require_student_role` / `_validate_id` 两个 helper；create_booking / cancel_booking 加四关校验；移除吞异常 try/except；import BusinessException、get_user_role_codes |
| `apps/api/src/app/ai/agent/runtime.py` | `__init__` 增加 `tenant_id` 参数并保存；`_handle_business_error` 改中文关键词匹配 + 安全兜底 |
| `apps/api/tests/test_mcp_tool_authorization.py` | 新增 18 用例 |

## Exact Fix

### 四关顺序（写 Tool）

```python
# 1. Authentication
if user_id is None:
    raise BusinessException("未提供用户身份，请先登录", code=401)
# 4. Input Validation（无需 DB，先于开 session）
_validate_id(schedule_id, "排期")
# 2. Authorization（在租户上下文中查角色）
async with SessionLocal() as db:
    await _require_student_role(db, user_id, "预约课程")
    # → BookingService（第 3 关 Tenant Validation 由 set 上下文/ORM 租户事件链路保证）
```

- 授权复用 `app.core.rbac.get_user_role_codes`（F2.2 引入，JOIN user_roles+roles，含全局角色，异常/无角色返回空集 → 最小权限默认拒绝）；
- `_validate_id`：`not isinstance(value, int) or isinstance(value, bool) or value <= 0` → 400；
- cancel_booking 额外校验 reason 类型与长度（≤200）；
- 异常不再被 Tool 捕获，传播到 Runtime 由 `_handle_business_error` 处理。

### 错误映射（runtime.py）

中文关键词列表（约满/已预约/余额不足/扣次失败/未找到/取消截止/已开始/两周/已取消/状态/学员身份/无效），命中返回不含原始异常子串的友好文案；兜底固定返回"⚠️ 操作失败，请稍后重试或联系客服"。

## Verification Plan

1. `pytest tests/test_mcp_tool_authorization.py -v`：18 用例；
2. `pytest tests/test_agent_runtime.py`：F5.3 错误映射 10/10、意图识别通过；
3. 回归 `test_auth_api` / `test_rbac_enforcement`；
4. py_compile 两个源文件；
5. grep 证明 Tool 无 Repository 直调 / 裸 SQL / Redis 业务读写。

## UNKNOWN

- 当前 mcp_server 的 Tool 签名没有 `tenant_id` 参数（与历史摘要描述不同，以当前代码为准）；租户隔离依赖 ORM 租户事件在请求 ContextVar 已设置的前提下生效。stdio MCP 独立会话场景的显式 tenant 传递属于更大议题，不在本 Feature 范围，登记为后续观察项。
- 查询类 Tool（get_my_bookings/get_my_balance）目前仍用裸 `select` / 透传 user_id，违反"Tool 只调 Service"的严格度，不在 F5.2 Scope（backlog 仅要求写操作），建议另立债务项。
