# F5.3 — Implementation Report

> Feature: F5.3 AI 异常处理不泄露原始信息
> 阶段：DEVELOPMENT → STATIC VERIFICATION → TESTING 完成
> 日期：2026-09-27

## Changed Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/ai/agent/runtime.py` | 重写 `_handle_business_error`：英文 error_map → 中文关键词子串匹配；兜底不回显原始异常 |
| 2 | `apps/api/tests/test_agent_runtime.py` | 新增 `test_business_error_handling()`，10 个用例断言关键词命中 + 原文不泄露 |

## Exact Changes

### 1. runtime.py — `_handle_business_error`

**修改前**：
- `error_msg = str(error).upper()`
- 英文 `error_map`（`SCHEDULE_FULL`、`BALANCE_INSUFFICIENT` 等）做 `code in error_msg`
- 兜底：`f"⚠️ 处理请求时出错：{error}\n请稍后重试或联系客服"`（回显原始异常）

**修改后**：
- `error_msg = str(error)`（不 upper）
- 中文关键词 `in` 子串匹配，覆盖 Service 层实际消息：约满 / 重复预约·已预约 / 余额不足·扣次失败 / 未找到·找不到 / 取消截止·不可取消 / 已开始 / 两周 / 已取消 / 签到·完成·状态
- 每条友好提示的完整文本**不包含原始异常字符串**（防"伪友好"泄露）
- 兜底：`"⚠️ 操作失败，请稍后重试或联系客服"`（不含 error）

### 2. test_agent_runtime.py — `test_business_error_handling`

- 10 个用例，输入为 Service 层实际抛出的中文异常消息
- 双断言：`keyword in result`（友好映射命中）**且** `original not in result`（不泄露原文）
- 包含未知异常用例（含 "SQL: SELECT * FROM"）验证兜底

## Scope Verification

- ✅ 实际修改文件 ⊆ 白名单 2 文件（runtime.py / test_agent_runtime.py）
- ✅ `_handle_business_error` 方法体外的 runtime.py 预存改动（tenant_id 注入、SYSTEM_PROMPT）未触碰
- ✅ mcp_server.py 未修改
- ✅ Service 层异常消息未修改
- ✅ 无 OpenAPI 契约变更（`/ai/chat` 请求/响应不变）

## Tests Run

| 套件 | 结果 | 说明 |
|------|------|------|
| `test_business_error_handling()` | ✅ 10/10 通过 | 所有用例关键词命中且原文不泄露 |
| `python3 -m py_compile runtime.py` | ✅ OK | |
| `python3 -m py_compile test_agent_runtime.py` | ✅ OK | |

## Results

- **AC-1（主验收）PASS**：9 类业务异常均映射为友好提示，且完整原始字符串不在输出中
- **AC-2 PASS**：未知异常兜底返回通用提示，不含 SQL 等技术细节
- **AC-3 PASS**：英文 error_map 已移除，改用中文关键词子串匹配
- **AC-4 PASS**：变更范围 ⊆ 2 文件白名单，py_compile 通过
- **AC-5 PASS**：测试全绿

## Risks

1. **Service 层消息微调**：若 Service 层修改了异常消息措辞（如"约满"→"名额已满"），关键词可能不匹配 → 走兜底（仍安全，不泄露）。后续可按需补充关键词。
2. **非业务异常混入**：`_handle_business_error` 接收所有 Exception，非业务异常（如 AttributeError）走兜底不回显，安全；但日志层未记录原始异常（属可观测性范畴，不在 F5.3）。

## UNKNOWN

- 生产环境 AI 对话中实际触发各业务异常的频率（需上线后监控，属可观测性）
- Service 层未来新增的异常消息关键词（按需补充）

## Handoff

- 执行 Agent：主 Agent（单一，mcp-engineer 领域）
- 下一阶段：REVIEW → ACCEPTANCE → CLOSE
- 验收入口：`cd apps/api && PYTHONPATH=src .venv/bin/python -c "import asyncio,sys; sys.path.insert(0,'tests'); from test_agent_runtime import test_business_error_handling; asyncio.run(test_business_error_handling())"`
