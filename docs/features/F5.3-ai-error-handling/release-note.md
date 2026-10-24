# F5.3 — Release Note

> Feature: AI 异常处理不泄露原始信息
> 关闭日期：2026-09-27
> 状态：DONE

## Feature

AI 对话中的业务异常返回用户友好提示，不回显内部异常、SQL、堆栈等技术细节。

## Problem

`AgentRuntime._handle_business_error` 存在两个缺陷：

1. **映射永不命中**：error_map 的 key 是英文枚举（`SCHEDULE_FULL` 等），但 Service 层抛出的 `BusinessException.msg` 是中文（如"该排期已约满"）。英文 key 永远匹配不到中文消息 → 所有业务异常都走兜底分支。
2. **兜底泄露原始异常**：兜底返回 `f"⚠️ 处理请求时出错：{error}..."`，直接把 `str(error)` 回显给用户。模式上违反"不回显原始异常"的安全原则，未来若有非业务异常混入（如 SQL 错误）会直接泄露技术细节。

## Fix

最小补丁，仅修改 `_handle_business_error` 一个方法：

1. **英文 error_map → 中文关键词子串匹配**：用 `"约满" in error_msg` 等中文关键词匹配 Service 层实际消息，容错消息微调。
2. **兜底不回显 error**：未知异常统一返回 `"⚠️ 操作失败，请稍后重试或联系客服"`。
3. **防"伪友好"泄露**：每条友好提示的完整文本刻意避开原始异常字符串（如"该排期已约满"→"该时段刚被约满"），确保原文不是输出的子串。

## Files Changed

| 文件 | 改动 |
|------|------|
| `apps/api/src/app/ai/agent/runtime.py` | 重写 `_handle_business_error`：中文关键词匹配 + 安全兜底 |
| `apps/api/tests/test_agent_runtime.py` | 新增 `test_business_error_handling()`，10 用例断言关键词命中 + 原文不泄露 |

## Tests

- `test_business_error_handling()`：**10/10 通过**
  - 9 类业务异常（约满、重复预约、余额不足、未找到、取消超时、课程已开始、预约过远、已取消、状态非法）均映射为友好提示且不含完整原文
  - 未知异常（含 SQL）兜底返回通用提示，不泄露技术细节
- `python3 -m py_compile`：2 文件均通过

## Acceptance

| AC | 判定 |
|----|------|
| AC-1 业务异常友好映射且不泄露原文 | ✅ PASS |
| AC-2 未知异常兜底不泄露 | ✅ PASS |
| AC-3 映射机制修正（中文关键词） | ✅ PASS |
| AC-4 变更范围 ⊆ 2 文件白名单 | ✅ PASS |
| AC-5 测试全绿 | ✅ PASS |

Review 结论：**READY_FOR_ACCEPTANCE** → **CLOSE**。

## Known Risks

1. **Service 层消息微调**：若 Service 层修改异常消息措辞，关键词可能不匹配 → 走兜底（仍安全，不泄露）。后续按需补充关键词。
2. **非业务异常混入**：`_handle_business_error` 接收所有 Exception，非业务异常走兜底不回显（安全）；但日志层未记录原始异常（属可观测性范畴，不在 F5.3）。

## Release Notes

- AI 对话遇到业务异常（约满、重复预约、余额不足等）时，返回对应用户友好提示并附带操作引导。
- 遇到未知异常时，返回"操作失败，请稍后重试或联系客服"，不回显内部异常、SQL、堆栈等技术细节。
- 无 API 契约变更（`/api/v1/ai/chat` 请求/响应结构不变）；前端无需改动。
- 四端（admin/student/teacher/miniapp）零影响（仅 AI 回复文本内容优化）。
