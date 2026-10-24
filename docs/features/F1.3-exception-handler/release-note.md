# F1.3 — Release Note

> Feature: 通用异常处理器 + 生产 debug 关闭
> 关闭日期：2026-09-26
> 状态：DONE

## Feature

未捕获异常返回标准化 500 信封，不泄露 traceback；生产环境 `APP_DEBUG=False`；修复 AI router 异常属性 bug。

## Problem

1. **无通用 Exception handler**：`main.py` 仅注册了 `DanceSaasException` 和 `IntegrityError`，未捕获异常在 debug=True 时泄露 traceback，debug=False 时返回非统一信封的 `{"detail":"Internal Server Error"}`。
2. **APP_DEBUG 默认 True**：生产环境若忘改 `.env`，debug 模式开启导致 traceback 泄露 + SQL echo。
3. **AI router 异常属性 bug**：`ai/router.py` 访问 `e.status_code` / `e.message`（`DanceSaasException` 实际属性为 `code` / `msg`），触发 AttributeError 导致所有业务异常降级为 500；且返回 `HTTPException` 非统一信封。

## Fix

最小补丁，4 个文件：

1. **新增通用 Exception handler**（`error_handler.py`）：`logger.exception` 记录完整堆栈到服务端日志，返回统一信封 `{code:500, msg:"服务暂时不可用，请稍后重试", request_id}`，响应体不含原始异常。
2. **APP_DEBUG 默认 False**（`config.py`）：开发环境 `.env` 已设 `APP_DEBUG=true` 覆盖，不受影响。
3. **移除 AI router 本地 try/except**（`ai/router.py`）：异常交全局 handler 统一处理，返回正确状态码 + 统一信封。

## Files Changed

| 文件 | 改动 |
|------|------|
| `apps/api/src/app/middleware/error_handler.py` | 新增 `unhandled_exception_handler` |
| `apps/api/src/app/main.py` | 注册通用 Exception handler |
| `apps/api/src/app/core/config.py` | `APP_DEBUG` 默认值改为 False |
| `apps/api/src/app/modules/ai/router.py` | 移除 3 个端点的本地 try/except |
| `apps/api/tests/test_exception_handlers.py` | 新建 7 个单元测试 |

## Tests

- `test_exception_handlers.py`：**7/7 通过**
  - 5 个 handler 测试：500 状态码、统一信封、不泄露原始消息、request_id、JSON content-type
  - 2 个 APP_DEBUG 默认值测试
- 冒烟验证：422 校验错误不回归；500 统一信封不泄露
- F5.3 回归：`test_business_error_handling` 10/10 通过

## Acceptance

| AC | 判定 |
|----|------|
| AC-1 未捕获异常 → 500 统一信封，不泄露 | ✅ PASS |
| AC-2 APP_DEBUG 默认 False | ✅ PASS |
| AC-3 AI 端点异常正确处理 + 统一信封 | ✅ PASS |
| AC-4 422 / 现有 handler 不回归 | ✅ PASS |
| AC-5 变更范围 ⊆ 白名单 | ✅ PASS |

Review 结论：**READY_FOR_ACCEPTANCE** → **CLOSE**。

## Known Risks

1. **生产 `.env` 配置**：需确保生产环境 `.env.prod` 不设 `APP_DEBUG=true`（或不设该变量），否则默认值 False 会被覆盖。
2. **AI 端点 500 响应 msg 变化**：从自定义格式变为统一信封，符合项目契约，前端应已兼容。

## Release Notes

- 所有未捕获异常现在返回统一信封 `{code:500, msg:"服务暂时不可用，请稍后重试"}`，不再泄露 traceback / SQL / 内部路径。
- 生产环境 `APP_DEBUG` 默认为 False，需显式开启 debug 模式。
- AI 端点的业务异常（401/403/404 等）现在返回正确的 HTTP 状态码和统一信封（之前因属性 bug 全部降级为 500）。
- 无 API 契约变更（仅错误响应内容优化）；四端前端无需改动。
