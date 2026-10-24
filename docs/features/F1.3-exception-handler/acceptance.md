# F1.3 — Acceptance Criteria

> 每条可独立判定 PASS / FAIL。
> 主 AC 为 AC-1；全部 AC 通过方可进入 REVIEW / ACCEPTANCE。

## AC-1 未捕获异常返回统一信封 500 且不泄露（主验收标准）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-1.1 | 未捕获异常 → HTTP 500 | TC-01 |
| AC-1.2 | 响应体为统一信封 `{code:500, msg, data:null, request_id}` | TC-01 |
| AC-1.3 | 响应体不含 traceback / SQL / 内部路径 / 原始异常消息 | TC-02 |
| AC-1.4 | 服务端日志（logger.exception）记录完整堆栈 | 代码审查 |

## AC-2 APP_DEBUG 默认 False

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-2.1 | `config.py` 中 `APP_DEBUG` 默认值为 `False` | 代码审查 + TC-04 |
| AC-2.2 | 开发环境 `.env` 仍可覆盖为 `True` | 代码审查（.env 已有 APP_DEBUG=true） |

## AC-3 AI 端点异常处理修复

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-3.1 | AI 端点 DanceSaasException 返回正确 HTTP 状态码（不再全降级为 500） | TC-05 |
| AC-3.2 | AI 端点异常响应为统一信封（非 `{"detail":...}`） | TC-05 / TC-06 |
| AC-3.3 | AI 端点未捕获异常 → 500 统一信封，不泄露 | TC-06 |
| AC-3.4 | AI 端点成功响应不变 | TC-07 |

## AC-4 回归

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-4.1 | 422 校验错误行为不回归（仍由 FastAPI 内置处理） | TC-08 |
| AC-4.2 | 现有 DanceSaasException / IntegrityError handler 不回归 | TC-09 / 代码审查 |

## AC-5 变更范围（静态）

| # | 标准 | 验证方式 |
|---|------|---------|
| AC-5.1 | 实际修改文件 ⊆ {error_handler.py, main.py, config.py, ai/router.py} | minimal-change-guard |
| AC-5.2 | 无 OpenAPI 契约变更（仅错误响应内容优化） | OpenAPI diff 审查 |
| AC-5.3 | 每个修改的 Python 文件通过 `python3 -m py_compile` | STATIC 记录 |

## 判定规则

- 任何 AC-1.x FAIL → Feature 整体 FAIL
- AC-2 ~ AC-5 中出现 FAIL → NEEDS_FIX 回到 DEVELOPMENT
