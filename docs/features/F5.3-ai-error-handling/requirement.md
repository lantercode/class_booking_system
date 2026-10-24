# F5.3 — AI 异常处理不泄露原始信息 · Requirement

> Feature ID：F5.3（Epic 5 / Phase 1 / P1）
> 阶段：REQUIREMENT（2026-09-26）

## Goal

AI 对话中的业务异常返回用户友好提示，不回显内部异常、SQL、堆栈等技术细节。

## Problem

`AgentRuntime._handle_business_error`（`ai/agent/runtime.py:336-377`）存在两个问题：

1. **映射永不命中**：error_map 的 key 是英文枚举（`SCHEDULE_FULL`、`BALANCE_INSUFFICIENT` 等），但匹配逻辑是 `str(error).upper()`，而 Service 层抛出的 `BusinessException.msg` 是中文（如"该排期已约满"、"只能预约未来两周内的课程"）。英文 key 永远匹配不到中文消息，所有业务异常都走兜底分支。
2. **兜底泄露原始异常**：兜底返回 `f"⚠️ 处理请求时出错：{error}\n请稍后重试或联系客服"`，直接把 `str(error)`（原始中文异常消息）回显给用户。当前消息本身还算友好，但模式上违反"不回显原始异常"的安全原则，且未来若有非业务异常混入会直接泄露。

## Scope

仅修改 `ai/agent/runtime.py` 的 `_handle_business_error` 方法：
1. error_map key 改为中文关键词子串匹配（对应 Service 层实际抛出的消息）
2. 兜底分支不回显 `error`，返回通用友好提示

## Out of Scope

- 不引入业务错误码枚举体系（需改 Service 层所有抛异常处，超出本 Feature）
- 不修改 mcp_server.py（Tool 异常已按 ai/mcp.md 合规传播给 Runtime）
- 不修改 Service 层异常消息
- 不修改前端

## User Roles

学员（通过 AI 对话预约/取消课程时遇到业务异常的终端用户）。

## Business Rules

1. 已知业务异常 → 返回对应友好提示（含引导动作）。
2. 未知异常 → 返回通用提示"操作失败，请稍后重试或联系客服"，不回显原始异常文本。
3. 异常映射基于中文消息子串匹配（`in`），容错消息微调。

## Dependencies

无前置 Feature；依赖 `BusinessException` 的中文 msg（已存在）。

## Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| Service 层消息微调导致子串不匹配 | 低 | 用核心关键词（如"约满"、"两周"）而非完整句子 |
| 非业务异常（如 AttributeError）混入 | 中 | 兜底不回显 error，统一通用提示；日志层记录原始异常（不在本 Feature，属可观测性） |

## Acceptance Criteria（摘要）

- AC-1：触发"该排期已约满"→ 返回友好提示，不含原始异常文本
- AC-2：触发未知异常 → 返回通用提示，不含 `str(error)`
- AC-3：其他已知业务异常（重复预约、余额不足、取消超时等）映射正确
