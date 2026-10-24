# F1.3 — 通用异常处理器 + 生产 debug 关闭 · Requirement

> Feature ID：F1.3（Epic 1 / Phase 1 / P0）
> 阶段：REQUIREMENT（2026-09-26）

## Goal

未捕获异常返回标准化 500 信封，不泄露 traceback；生产环境 `APP_DEBUG=False`；修复 AI router 异常属性 bug。

## Problem

### P1：无通用 Exception handler（安全）

`main.py:163-164` 仅注册了 `DanceSaasException` 和 `IntegrityError` 两个异常处理器。任何未捕获的异常（`AttributeError`、`KeyError`、`TypeError` 等）会走 FastAPI 默认处理：

- `debug=True` 时：返回**完整 traceback**（泄露内部代码路径、SQL、变量）
- `debug=False` 时：返回 `{"detail": "Internal Server Error"}`（**非统一信封** `{code,msg,data}`，前端解包失败）

### P2：APP_DEBUG 默认 True（安全）

`config.py:35` `APP_DEBUG: bool = True`。若生产环境 `.env` 未显式设置 `APP_DEBUG=false`，则 debug 模式开启，traceback 泄露。同时 `database.py:11` `echo=settings.APP_DEBUG` 会在生产环境打印全部 SQL。

### P3：AI router 异常处理 bug（功能 + 安全）

`ai/router.py:86-87`：

```python
except DanceSaasException as e:
    raise HTTPException(status_code=e.status_code, detail=e.message)
```

`DanceSaasException` 的属性是 `code` 和 `msg`（`core/exceptions.py:2-5`），**不存在** `status_code` / `message`。此处会触发 `AttributeError`，被外层 `except Exception` 捕获，返回 500，导致业务异常（如 401、403、404）全部降级为 500，丢失正确的 HTTP 状态码与业务消息。

此外，`ai/router.py` 的 `except Exception` 分支返回 `HTTPException(status_code=500, detail=...)`，响应体是 FastAPI 默认格式 `{"detail": "..."}` 或自定义 dict，**不是统一信封** `{code, msg, data}`，与项目其他端点不一致。

## Scope

1. **T1.3.1**：注册 `@app.exception_handler(Exception)` 通用处理器，返回统一信封 500，日志记录完整异常
2. **T1.3.2**：`config.py` `APP_DEBUG` 默认值改为 `False`（开发环境 `.env` 已设 `APP_DEBUG=true`，不受影响）
3. **T1.3.3**：移除 `ai/router.py` 中 chat/history/clear_history 的本地 try/except，让全局异常处理器统一处理

## Out of Scope

- 不修改 `DanceSaasException` 体系与子类
- 不修改 `dance_saas_exception_handler` / `integrity_error_handler` 现有行为
- 不修改前端
- 不修改 Service 层抛异常逻辑
- 不引入 Sentry/APM 等外部可观测性组件（仅本地 logger.exception）

## User Roles

全部 API 消费者（前端四端 + 小程序），受影响的是 500 错误时的响应格式与安全性。

## Business Rules

1. 未捕获异常 → HTTP 500 + 统一信封 `{code:500, msg:"服务暂时不可用，请稍后重试", data:null}`，响应体**不含** traceback / SQL / 内部路径
2. 服务端日志（logger.exception）记录完整异常堆栈，便于排查
3. `APP_DEBUG` 默认 `False`；开发环境通过 `.env` 显式开启
4. AI 端点的异常响应与其他端点格式一致（统一信封）

## Dependencies

无前置 Feature。

## Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 通用 Exception handler 覆盖 FastAPI 内置 422（RequestValidationError）等 | 中 | FastAPI 按 MRO 匹配最具体 handler；`RequestValidationError` 等内置异常 FastAPI 已注册具体 handler，优先级高于 `Exception`。需验证 422 行为不回归 |
| 移除 ai/router.py 本地 try/except 后，AI 500 响应 msg 变化 | 低 | 统一为"服务暂时不可用"，更安全；前端不依赖具体 msg |
| APP_DEBUG=False 导致开发环境 SQL echo 关闭 | 低 | `.env` 已设 `APP_DEBUG=true`，开发不受影响 |

## Acceptance Criteria（摘要）

- AC-1：触发未捕获异常 → HTTP 500，响应体为统一信封，无 traceback
- AC-2：`APP_DEBUG` 默认值为 `False`
- AC-3：AI 端点业务异常（DanceSaasException）返回正确 HTTP 状态码 + 统一信封
- AC-4：现有 422 校验错误行为不回归
