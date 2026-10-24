# F5.2 — Implementation Report

## 实施概述

按四关校验要求改造两个写操作 Tool，并修复两个阻断授权链路的连带问题。

## 变更明细

### 1. mcp_server.py

**新增 import**
- `from app.core.exceptions import BusinessException`
- `from app.core.rbac import get_user_role_codes`

**新增两个 helper（STATUS_LABELS 之后）**
- `_require_student_role(db, user_id, action)`：调 RBAC 核心查角色集合，不含 `student` 即抛 `BusinessException(code=403)`；
- `_validate_id(value, name)`：非 int / bool / ≤0 抛 `BusinessException(code=400)`。

**create_booking**
- `user_id is None` → 401（原为返回字符串）；
- `_validate_id(schedule_id, "排期")`；
- session 内 `_require_student_role(..., "预约课程")` 通过后才调 `BookingService.create_booking`；
- 删除 `except Exception: return f"预约失败：{e}"`，异常向 Runtime 传播。

**cancel_booking**
- 同构 401 / 角色 403；
- `_validate_id(booking_id, "预约")`；
- reason 校验：非 str → 400；长度 >200 → 400；
- Service 归属校验保持不变（`cancel_booking(student_id=user_id)`）；
- 删除吞异常 except。

### 2. runtime.py

- `__init__(self, redis_client=None, user_id=None, tenant_id=None)`：补 `tenant_id` 参数与 `self.tenant_id`（修复 AI router 传参导致的 TypeError）；
- `_handle_business_error`：英文错误码映射 → 中文关键词匹配（14 条），兜底不回显原文。友好文案刻意改写措辞，确保不把原始异常消息作为子串包含。

### 3. test_mcp_tool_authorization.py（新增）

- `TestValidateId`：6 用例（合法 / 0 / 负数 / 字符串 / bool / None）；
- `TestCreateBookingAuthorization`：5 用例（401、400×3、非学员 403 + Service spy）；
- `TestCancelBookingAuthorization`：4 用例（401、400、reason 超长、非学员 403 + spy）；
- `TestAuthorizationFriendlyMessage`：3 用例（学员身份映射不泄露、无效参数映射、未知异常不含 SQL）。

## 关键设计决策

1. **角色查询用 RBAC 核心而非 HTTP 装饰器**：Tool 以 Python 函数方式被 Runtime 直接调用，无法走 FastAPI Depends；`get_user_role_codes` 是 RBAC 基础设施查询函数，符合 mcp.md"Tool 必须独立完成授权判断"。
2. **空角色集合默认拒绝**：无角色账号、查询异常均落入非学员分支，最小权限。
3. **角色关与归属关分离**：角色关回答"能不能做这类操作"，Service 归属关回答"能不能操作这条数据"，二者均保留。
4. **Input 校验前置于开 session**：纯内存检查不占 DB 连接。
