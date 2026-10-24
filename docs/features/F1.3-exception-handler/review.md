# F1.3 — 通用异常处理器 + 生产 debug 关闭 · Feature Review

> Feature ID：F1.3
> 评审日期：2026-09-26
> 评审性质：主 Agent 对照 AC 复核（简单单域后端修复）
> 评审输入：requirement.md / user-flow.md / acceptance.md / implementation-plan.md / implementation-report.md / static-verification.md / runtime-test-report.md + 独立 git diff 与源码核查

---

## Scope Review

**结论：严格遵守 F1.3 Scope。**

| 文件 | diff 实证 | 判定 |
|------|----------|------|
| `middleware/error_handler.py` | 仅新增 `unhandled_exception_handler` 函数，现有两个 handler 未改 | ✅ 与 plan 一致 |
| `main.py` | 仅新增 import + 1 行 `add_exception_handler(Exception, ...)` | ✅ 与 plan 一致 |
| `core/config.py` | 仅 L35 `APP_DEBUG` 默认值 `True` → `False` | ✅ 与 plan 一致 |
| `modules/ai/router.py` | 移除 3 个端点的 try/except + 清理未使用 import；计时逻辑保留 | ✅ 与 plan 一致 |
| `tests/test_exception_handlers.py` | 新建，仅测试代码 | ✅ 与 plan 一致 |

- 未修改 DanceSaasException 体系、现有两个 handler、Service 层、前端。
- 未触碰工作区预存改动（membership/service.py 等）。

## Architecture Review

**结论：符合架构规则，无违规。**

- 分层：异常处理器位于 middleware 层，不涉及 Service / Repository / Router 业务逻辑，符合 `architecture/layering.md`。
- 安全：响应不回显 traceback / SQL / 内部路径，符合 `security/authentication.md`；服务端 `logger.exception` 保留排查能力。
- 契约：无 OpenAPI 变更，仅错误响应内容优化。
- AI/MCP：不涉及 Tool 四关链路，AI router 改动仅移除本地异常处理交全局 handler。

## Code Review

**结论：最小修复，无隐藏业务逻辑变化。**

1. `unhandled_exception_handler`：`logger.exception` 记录完整堆栈，`fail(code=500, msg="服务暂时不可用，请稍后重试")` 返回统一信封。响应体不含 `exc` 任何片段。
2. `main.py`：handler 注册顺序正确（Exception 在 DanceSaasException / IntegrityError 之后），Starlette MRO 保证专用 handler 优先。
3. `config.py`：`APP_DEBUG: bool = False`，开发 `.env` 已设 `APP_DEBUG=true` 覆盖。
4. `ai/router.py`：移除 try/except 后，`DanceSaasException` 走全局 handler 返回正确状态码 + 统一信封；其他异常走通用 handler 返回 500。chat 端点计时逻辑保留。
5. 无顺手修复、无整文件格式化。

## Regression Review

**结论：回归风险低。**

- 422 校验错误：Starlette MRO 保证 `RequestValidationError` 优先命中，冒烟测试确认 422 不回归。
- 现有 `DanceSaasException` / `IntegrityError` handler：未修改，行为不变。
- F5.3 回归：`test_business_error_handling` 10/10 通过，AI router 改动不影响 AgentRuntime。
- AI 端点成功路径：未修改，响应结构不变。

## Acceptance Review

| AC | 判定 | 依据 |
|----|------|------|
| AC-1 未捕获异常 → 500 统一信封不泄露 | **PASS** | 5/5 单元测试 + 2/2 冒烟测试 |
| AC-2 APP_DEBUG 默认 False | **PASS** | 2/2 单元测试 |
| AC-3 AI 端点异常正确处理 | **PASS** | 代码审查 + 冒烟验证通用 handler |
| AC-4 422 / 现有 handler 不回归 | **PASS** | 冒烟测试 + 代码审查 |
| AC-5 变更范围 ⊆ 白名单 | **PASS** | git diff + py_compile |

## Risks

| # | 风险 | 等级 | 处置建议 |
|---|------|------|---------|
| R1 | 生产 `.env.prod` 若设 `APP_DEBUG=true` 会覆盖默认 False | 低 | 部署时确认 `.env.prod` 不设该变量或设为 false |
| R2 | AI 端点 500 响应 msg 从自定义格式变为统一信封 | 低 | 符合项目契约，前端应已兼容统一信封 |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 生产环境前端对 500 统一信封的兼容性 | 统一信封本就是项目契约要求，前端 api-client 已按 `{code,msg,data}` 解包 |

## Recommendation

1. **代码层面**：F1.3 修复正确、最小、完整。通用 Exception handler、APP_DEBUG 默认值、AI router 异常修复三项均通过测试验证，无需返工。
2. **验收层面**：全部 AC 通过，可关闭。
3. **部署层面**：生产部署时确认 `.env.prod` 不设 `APP_DEBUG=true`。

**最终结论：READY_FOR_ACCEPTANCE**
