# F1.3 — 通用异常处理器 + 生产 debug 关闭 · 实施方案

> Feature ID：F1.3
> 日期：2026-09-26
> 性质：最小补丁（4 文件），复用既有 `fail()` 统一信封与 `logger`
> 关联文档：[requirement.md](./requirement.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

### 问题 1：无通用 Exception handler（安全）

- `main.py:163-164` 仅注册了 `DanceSaasException` 和 `IntegrityError` 两个异常处理器。
- 未捕获异常（`AttributeError`、`KeyError`、`TypeError` 等）走 FastAPI 默认处理：
  - `debug=True` 时：返回**完整 traceback**（泄露内部代码路径、SQL、变量）
  - `debug=False` 时：返回 `{"detail": "Internal Server Error"}`（**非统一信封**，前端解包失败）

### 问题 2：APP_DEBUG 默认 True（安全）

- `config.py:35` `APP_DEBUG: bool = True`。
- 生产环境若 `.env` 未显式设置 `APP_DEBUG=false`，则 debug 模式开启，traceback 泄露。
- 同时 `database.py:11` `echo=settings.APP_DEBUG` 会在生产环境打印全部 SQL。

### 问题 3：AI router 异常处理 bug（功能 + 安全）

- `ai/router.py:86-87`：`except DanceSaasException as e: raise HTTPException(status_code=e.status_code, detail=e.message)`
- `DanceSaasException` 的属性是 `code` 和 `msg`（`core/exceptions.py:2-5`），**不存在** `status_code` / `message`。
- 此处触发 `AttributeError`，被外层 `except Exception` 捕获，返回 500，导致业务异常（401、403、404）全部降级为 500。
- 此外 `except Exception` 分支返回 `HTTPException`，响应体为 FastAPI 默认格式 `{"detail": ...}`，**非统一信封**。

---

## Affected Files

| # | 文件 | 改动内容 |
|---|------|---------|
| 1 | `apps/api/src/app/middleware/error_handler.py` | 新增 `unhandled_exception_handler` |
| 2 | `apps/api/src/app/main.py` | 注册 `app.add_exception_handler(Exception, ...)` |
| 3 | `apps/api/src/app/core/config.py` | `APP_DEBUG` 默认值 `True` → `False` |
| 4 | `apps/api/src/app/modules/ai/router.py` | 移除 3 个端点的本地 try/except，交全局 handler |
| 5 | `apps/api/tests/test_exception_handlers.py` | 新建 7 个单元测试 |

---

## Exact Fix

### 1. error_handler.py — 新增通用 Exception handler

```python
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"[UnhandledException] path={request.url.path}")
    info = fail(code=500, msg="服务暂时不可用，请稍后重试")
    return JSONResponse(status_code=500, content=info)
```

- 服务端日志记录完整堆栈（`logger.exception`），客户端响应不泄露。
- 返回统一信封 `{code:500, data:null, msg, request_id}`。

### 2. main.py — 注册 handler

L169 新增：`app.add_exception_handler(Exception, unhandled_exception_handler)`（位于 DanceSaasException / IntegrityError 之后）。

**优先级保证**：Starlette `ExceptionMiddleware._lookup_exception_handler` 按异常 MRO 查找最具体 handler。已注册的 `DanceSaasException`、`IntegrityError` 以及 FastAPI 内置的 `RequestValidationError` 均比 `Exception` 更具体，优先级更高，不受影响。

### 3. config.py — APP_DEBUG 默认 False

L35：`APP_DEBUG: bool = True` → `APP_DEBUG: bool = False`。
开发环境 `.env` 已设 `APP_DEBUG=true`，运行时覆盖默认值，不受影响。

### 4. ai/router.py — 移除本地 try/except

- chat 端点：移除 `except DanceSaasException`（属性 bug）和 `except Exception`（非统一信封），保留 `start_time` / `latency_ms` 计时。
- history / clear_history 端点：移除 `try/except Exception`。
- 清理未使用的 import（`HTTPException`、`DanceSaasException`）。

### 5. test_exception_handlers.py — 新建

- `TestUnhandledExceptionHandler`：5 个用例（500 状态码、统一信封字段、不泄露原始消息、request_id 存在、content-type JSON）。
- `TestAppDebugDefault`：2 个用例（默认值 False、类型 bool）。

---

## Why This Fix Is Sufficient

1. 通用 Exception handler 作为最后一道防线，确保所有未捕获异常返回统一信封 500，不泄露 traceback / SQL / 内部路径。
2. 服务端 `logger.exception` 保留完整堆栈供排查，与响应脱敏不矛盾。
3. `APP_DEBUG=False` 默认值确保生产环境安全；开发环境通过 `.env` 显式开启。
4. 移除 AI router 本地 try/except 后，`DanceSaasException` 走全局 handler 返回正确状态码 + 统一信封，其他异常走通用 handler 返回 500 统一信封。

---

## Verification Plan

| AC 编号 | 验证方式 |
|---------|---------|
| AC-1.1 ~ AC-1.4 | 直调 `unhandled_exception_handler` + 冒烟测试（TestClient 触发未捕获异常） |
| AC-2.1 ~ AC-2.2 | 代码审查 + `Settings.model_fields["APP_DEBUG"].default is False` |
| AC-3.1 ~ AC-3.4 | 冒烟测试（mock AgentRuntime 抛异常）+ 代码审查 |
| AC-4.1 ~ AC-4.2 | 冒烟测试（422 校验）+ 现有 handler 代码审查 |
| AC-5.1 ~ AC-5.3 | minimal-change-guard + py_compile |

---

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 注册 `Exception` handler 是否影响 FastAPI 内置 422 | Starlette MRO 优先级保证 422 不受影响；冒烟测试已验证 |
| U2 | 移除 ai/router.py try/except 后 chat 端点的计时逻辑 | 成功路径计算 latency_ms；异常时由全局 handler 接管，无 latency_ms 属可接受行为 |
