# F5.3 — AI 异常处理不泄露原始信息 · Feature Review

> Feature ID：F5.3
> 评审日期：2026-09-27
> 评审性质：主 Agent 对照 AC 复核（简单单域 AI Runtime 修复）
> 评审输入：requirement.md / user-flow.md / acceptance.md / implementation-plan.md / implementation-report.md / static-verification.md / runtime-test-report.md + 独立 git diff 与源码核查

---

## Scope Review

**结论：严格遵守 F5.3 Scope。**

| 文件 | diff 实证 | 判定 |
|------|----------|------|
| `ai/agent/runtime.py` | 修改全部局限于 `_handle_business_error` 方法体；方法体外的预存改动（tenant_id、SYSTEM_PROMPT）未触碰 | ✅ 与 plan 一致 |
| `tests/test_agent_runtime.py` | 新增 `test_business_error_handling()` 函数，其余测试函数未改 | ✅ 与 plan 一致 |

- 未修改 mcp_server.py、Service 层异常消息、前端。
- 未触碰预存改动。

## Architecture Review

**结论：符合架构规则，无违规。**

- 分层：修改位于 AI Runtime 层（`ai/agent/runtime.py`），未触碰 Service / Repository / Router，符合 `architecture/layering.md`。
- AI 边界：AI 不直接落库、不绕 Service，符合 `ai/ai-architecture.md`。
- 安全：不回显内部异常、SQL、堆栈，符合 `ai/mcp.md` 输出安全要求。
- 契约：无 OpenAPI 变更（`/ai/chat` 请求/响应结构不变，仅 `data.response` 文本内容优化）。

## Code Review

**结论：最小修复，无隐藏业务逻辑变化。**

1. `_handle_business_error`：英文 error_map → 中文关键词 `in` 子串匹配，覆盖 Service 层实际中文消息。
2. 兜底：`"⚠️ 操作失败，请稍后重试或联系客服"`，不含 `error`。
3. 每条友好提示刻意避开原始整句，确保原文不是输出的子串（防"伪友好"泄露）。
4. 无顺手修复、无整文件格式化。
5. 测试双断言：`keyword in result` 且 `original not in result`。

## Regression Review

**结论：回归风险极低。**

- 仅修改 `_handle_business_error` 一个方法，不影响意图识别、Tool 调用、格式化等其他流程。
- AI chat 主流程（成功路径）未修改。
- 10/10 测试通过，含未知异常兜底不泄露验证。

## Acceptance Review

| AC | 判定 | 依据 |
|----|------|------|
| AC-1 业务异常友好映射且不泄露原文 | **PASS** | 9/9 用例双断言通过 |
| AC-2 未知异常兜底不泄露 | **PASS** | TC-10（含 SQL）通过 |
| AC-3 映射机制修正（中文关键词） | **PASS** | 代码审查无 error_map / .upper() |
| AC-4 变更范围 ⊆ 白名单 | **PASS** | git diff + py_compile |
| AC-5 测试全绿 | **PASS** | 10/10 通过 |

## Risks

| # | 风险 | 等级 | 处置建议 |
|---|------|------|---------|
| R1 | Service 层消息微调导致关键词不匹配 | 低 | 走兜底（仍安全不泄露）；后续按需补充关键词 |
| R2 | 非业务异常混入 _handle_business_error | 低 | 兜底不回显；日志层记录原始异常属可观测性范畴 |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 生产环境 AI 对话中实际触发各业务异常的频率 | 上线后监控（可观测性范畴） |

## Recommendation

1. **代码层面**：F5.3 修复正确、最小、完整。英文 error_map 改为中文关键词匹配，兜底不回显原始异常，所有 10 个用例通过双断言验证。
2. **验收层面**：全部 AC 通过，可关闭。

**最终结论：READY_FOR_ACCEPTANCE**
