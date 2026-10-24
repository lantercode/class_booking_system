# F5.2 — Static Verification

## 1. 编译检查

```bash
PYTHONPATH=src .venv/bin/python -c \
 "import py_compile; \
  py_compile.compile('src/app/ai/mcp_server.py', doraise=True); \
  py_compile.compile('src/app/ai/agent/runtime.py', doraise=True)"
# COMPILE_OK
```

测试文件同样可被 pytest 收集（18 用例全部 collected）。

## 2. 四关顺序核查（mcp_server.py）

```
272: # 第一关 Authentication          → user_id None → 401
276: # 第二关 Authorization + 第四关   → SessionLocal
278:     await _require_student_role  → 非 student → 403
279:     _validate_id(schedule_id)    → 非法 → 400
（第三关 Tenant Validation：ORM do_orm_execute 租户事件链，请求 ContextVar 由 tenant_middleware 设置）
307/311-318: cancel_booking 同构
```

顺序符合 `Authentication → Authorization → Tenant → Input`，无跳过、无调换。

## 3. 分层红线核查（写 Tool 区段 L260–330）

```bash
sed -n '260,330p' src/app/ai/mcp_server.py | grep -nE "Repository|execute\(|text\(|redis|SELECT|INSERT"
# 无匹配
```

- 写 Tool 只调用 `BookingService` 与 RBAC 核心 `get_user_role_codes`；
- 无 Repository 直连、无裸 SQL、无 Redis 业务读写；
- 未在 `ai/tools/` 新增任何注册（统一 FastMCP 单一注册点）。

## 4. 输出安全核查

- 写 Tool 已无 `except Exception: return f"...{e}"` 吞异常回显；
- `runtime._handle_business_error` 兜底为固定文案，不含 `{error}`；
- test_unknown_error_no_leak 断言 `SELECT`/`DROP` 不出现在回复中，通过。

## 5. 身份可信核查

- 写 Tool 的 user_id 唯一来源是 Runtime 调用入参，而 Runtime 由 `get_current_user` 注入（modules/ai/router.py L51-55）；
- 工具签名不暴露 tenant_id 给 LLM 覆盖；
- 未从 LLM 产出文本读取身份。

## 6. 契约核查

- `/api/v1/ai/chat` 的路径、请求体、响应模型均未改；
- Tool 是内部 Python 函数，不产生 OpenAPI 条目；
- 前端 4 端无需改动、无需重新生成 api-types。
