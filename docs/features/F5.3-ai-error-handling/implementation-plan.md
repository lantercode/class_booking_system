# F5.3 — AI 异常处理不泄露原始信息 · 实施方案

> Feature ID：F5.3
> 日期：2026-09-27
> 性质：最小补丁（仅改 `_handle_business_error` 一个方法），不引入新组件、不改 Service 层异常
> 关联文档：[requirement.md](./requirement.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

### 问题 1：异常映射永不命中

- `ai/agent/runtime.py:336-377` `_handle_business_error`：error_map 的 key 是英文枚举（`SCHEDULE_FULL`、`BALANCE_INSUFFICIENT` 等），匹配逻辑是 `str(error).upper()`。
- Service 层抛出的 `BusinessException.msg` 是中文（如"该排期已约满"）。
- 英文 key 永远匹配不到中文消息 → 所有业务异常都走兜底分支。

### 问题 2：兜底泄露原始异常

- 兜底返回 `f"⚠️ 处理请求时出错：{error}\n请稍后重试或联系客服"`，直接把 `str(error)`（原始中文异常消息）回显给用户。
- 模式上违反"不回显原始异常"的安全原则，未来若有非业务异常混入（如 SQL 错误）会直接泄露技术细节。

### 问题 3：部分友好消息与原文过于接近

- 部分分支的友好提示直接复用了原始整句（如"未找到该预约记录"→"未找到该预约记录"），虽然措辞友好但完整原始字符串仍出现在输出中，构成"伪友好"泄露。

---

## Affected Files

| # | 文件 | 改动内容 |
|---|------|---------|
| 1 | `apps/api/src/app/ai/agent/runtime.py` | 重写 `_handle_business_error`：英文 error_map → 中文关键词子串匹配；兜底不回显原始异常 |
| 2 | `apps/api/tests/test_agent_runtime.py` | 新增 `test_business_error_handling()`，10 个用例 |

---

## Exact Fix

### 1. runtime.py — 重写 `_handle_business_error`

**修改前**：
- `error_msg = str(error).upper()`
- 英文 `error_map`（`SCHEDULE_FULL`、`BALANCE_INSUFFICIENT` 等）做 `code in error_msg`
- 兜底：`f"⚠️ 处理请求时出错：{error}\n请稍后重试或联系客服"`（回显原始异常）

**修改后**：
- `error_msg = str(error)`（不 upper）
- 中文关键词 `in` 子串匹配，覆盖 Service 层实际消息：约满 / 重复预约·已预约 / 余额不足·扣次失败 / 未找到·找不到 / 取消截止·不可取消 / 已开始 / 两周 / 已取消 / 签到·完成·状态
- 每条友好提示的完整文本**不包含原始异常字符串**（防"伪友好"泄露）
- 兜底：`"⚠️ 操作失败，请稍后重试或联系客服"`（不含 error）

### 2. test_agent_runtime.py — 新增测试

- 10 个用例，输入为 Service 层实际抛出的中文异常消息。
- 双断言：`keyword in result`（友好映射命中）**且** `original not in result`（不泄露原文）。
- 包含未知异常用例（含 "SQL: SELECT * FROM"）验证兜底不泄露。

---

## Why This Fix Is Sufficient

1. 中文关键词子串匹配（如"约满"）比整句更抗 Service 层消息微调。
2. 兜底不回显 error，未知异常统一返回通用提示，不泄露技术细节。
3. 每条友好提示刻意避开原始整句，确保原文不是输出的子串。
4. 不修改 Service 层异常消息、不引入错误码枚举体系（超出 Scope）。

---

## Verification Plan

| AC 编号 | 验证方式 |
|---------|---------|
| AC-1.1 ~ AC-1.9 | `test_business_error_handling()` 9 类业务异常用例 |
| AC-2.1 ~ AC-2.2 | 未知异常用例（含 SQL）+ 代码审查 |
| AC-3.1 ~ AC-3.2 | 代码审查（无 error_map / .upper()） |
| AC-4.1 ~ AC-4.4 | minimal-change-guard + py_compile + diff 审查 |
| AC-5.1 ~ AC-5.2 | 测试全绿 + 代码审查 |

---

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | Service 层未来新增异常消息未覆盖关键词 | 兜底通用提示仍安全（不泄露）；后续按需补充关键词 |
| U2 | 非业务异常混入 `_handle_business_error` | 兜底不回显；日志层记录原始异常属可观测性范畴（不在 F5.3） |
