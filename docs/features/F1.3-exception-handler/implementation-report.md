# F1.3 — Implementation Report

> Feature: F1.3 通用异常处理器 + 生产 debug 关闭
> 阶段：DEVELOPMENT → STATIC VERIFICATION → TESTING 完成
> 日期：2026-09-26

## Changed Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/middleware/error_handler.py` | 新增 `unhandled_exception_handler`：logger.exception 记录 + fail() 返回 500 统一信封 |
| 2 | `apps/api/src/app/main.py` | 注册 `app.add_exception_handler(Exception, unhandled_exception_handler)` |
| 3 | `apps/api/src/app/core/config.py` | `APP_DEBUG` 默认值 `True` → `False` |
| 4 | `apps/api/src/app/modules/ai/router.py` | 移除 chat/history/clear_history 的本地 try/except，交全局 handler 统一处理 |
| 5 | `apps/api/tests/test_exception_handlers.py`（新建） | 7 个单元测试 |

## Exact Changes

### 1. error_handler.py — 新增通用 Exception handler

```python
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"[UnhandledException] path={request.url.path}")
    info = fail(code=500, msg="服务暂时不可用，请稍后重试")
    return JSONResponse(status_code=500, content=info)
```

- 服务端日志记录完整堆栈（`logger.exception`），客户端响应不泄露
- 返回统一信封 `{code:500, data:null, msg, request_id}`

### 2. main.py — 注册 handler

L169 新增：`app.add_exception_handler(Exception, unhandled_exception_handler)`（位于 DanceSaasException / IntegrityError 之后）

### 3. config.py — APP_DEBUG 默认 False

L35：`APP_DEBUG: bool = True` → `APP_DEBUG: bool = False`

### 4. ai/router.py — 移除本地 try/except

- chat 端点：移除 `except DanceSaasException`（属性 bug）和 `except Exception`（非统一信封），保留 `start_time` / `latency_ms` 计时
- history / clear_history 端点：移除 `try/except Exception`
- 清理未使用的 import（`HTTPException`、`DanceSaasException`）

### 5. test_exception_handlers.py — 新建

- `TestUnhandledExceptionHandler`：5 个用例（500 状态码、统一信封字段、不泄露原始消息、request_id 存在、content-type JSON）
- `TestAppDebugDefault`：2 个用例（默认值 False、类型 bool）

## Scope Verification

- ✅ 实际修改文件 ⊆ 白名单 4 文件 + 1 测试文件
- ✅ 未修改 DanceSaasException 体系、现有两个 handler、Service 层
- ✅ 未修改前端
- ✅ 未触碰工作区预存改动

## Tests Run

| 套件 | 结果 | 说明 |
|------|------|------|
| `test_exception_handlers.py` | ✅ 7 passed | handler 直调 + APP_DEBUG 默认值 |
| 冒烟：422 不回归 | ✅ PASS | FastAPI 内置 RequestValidationError handler 优先于 Exception handler（MRO） |
| 冒烟：500 统一信封不泄露 | ✅ PASS | status=500, code=500, 原始异常消息不在响应体 |
| F5.3 回归 `test_business_error_handling` | ✅ 10/10 | AI router 改动不影响 AgentRuntime |
| py_compile（5 文件） | ✅ 全部通过 | |

## Results

- **AC-1（主验收）PASS**：未捕获异常 → HTTP 500 统一信封，无 traceback / SQL / 原始消息
- **AC-2 PASS**：`APP_DEBUG` 默认 `False`
- **AC-3 PASS**：AI 端点异常由全局 handler 处理，返回正确状态码 + 统一信封
- **AC-4 PASS**：422 校验错误不回归；现有 DanceSaasException / IntegrityError handler 不回归
- **AC-5 PASS**：变更范围 ⊆ 白名单，py_compile 通过

## Risks

1. **`Exception` handler 优先级**：已验证 Starlette 按 MRO 匹配，`RequestValidationError`（422）等内置 handler 优先命中，不受影响。
2. **`.env` 覆盖**：项目根 `.env` 已设 `APP_DEBUG=true`，开发环境不受影响；生产部署需确保 `.env.prod` 不设 `APP_DEBUG=true`。
3. **AI 端点 500 响应 msg 变化**：从 `{"code":50001,"message":"AI 服务暂时不可用"}` 变为统一信封 `{code:500, msg:"服务暂时不可用，请稍后重试"}`，符合项目契约。

## UNKNOWN

- 无。

## Handoff

- 执行 Agent：backend-engineer（单一）
- 下一阶段：REVIEW → ACCEPTANCE → CLOSE
- 验收入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/test_exception_handlers.py -v`
