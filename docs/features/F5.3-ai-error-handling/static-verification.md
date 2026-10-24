# F5.3 — Static Verification

> 阶段：STATIC VERIFICATION
> 日期：2026-09-27

## 1. 范围守卫（minimal-change-guard）

### 1.1 白名单

```
apps/api/src/app/ai/agent/runtime.py
apps/api/tests/test_agent_runtime.py
```

### 1.2 范围复核结论

- ✅ 2 个白名单文件均在 `git diff --name-only` 中
- ✅ 白名单外，F5.3 相关目录（`ai/`）无其他文件被修改（mcp_server.py 未动）
- ✅ `git diff --check apps/api/src/app/ai/agent/runtime.py apps/api/tests/test_agent_runtime.py` → 无空白错误
- ⚠ `git diff --check`（全工作区）报告 `membership/service.py` 有 trailing whitespace —— 该文件为预存改动，非 F5.3 引入

### 1.3 逐文件 diff 审查

- **runtime.py**：修改全部局限于 `_handle_business_error` 方法体（L336-373）。方法体外的预存改动（`tenant_id` 注入、`SYSTEM_PROMPT` 引入）未触碰。
  - 移除：`error_map` 字典、`str(error).upper()`、兜底 `f"...{error}..."`
  - 新增：中文关键词 `in` 子串匹配链 + 安全兜底
- **test_agent_runtime.py**：新增 `test_business_error_handling()` 函数（10 用例），其余测试函数未改。

## 2. 编译验证

| 文件 | py_compile |
|------|-----------|
| `apps/api/src/app/ai/agent/runtime.py` | ✅ OK |
| `apps/api/tests/test_agent_runtime.py` | ✅ OK |

## 3. 契约验证（AC-4.2）

- 无新端点、无删除端点
- `/api/v1/ai/chat` 请求体不变（仍为 `{message, session_id?}`）
- `/api/v1/ai/chat` 响应体不变（仍为 `{code, msg, data:{reply}}`）
- 仅 AI 回复文本的**内容**变了（更友好、不泄露），结构不变

## 4. 防泄露审查

逐条核对友好提示是否包含完整原始异常字符串：

| 原始消息 | 友好提示 | 原文是子串？ |
|---------|---------|------------|
| `该排期已约满` | `❌ 该时段刚被约满 😢...` | 否（"该排期" vs "该时段"） |
| `您已预约该排期，请勿重复预约` | `❌ 您已预约过此课程...` | 否（第 5 字"该" vs "过"） |
| `会员卡扣次失败，预约已撤销` | `❌ 课时余额不足...` | 否 |
| `未找到该预约记录` | `❌ 未找到对应的预约记录...` | 否（"该" vs "对应的"） |
| `已超过取消截止时间` | `❌ 已过可取消时限...` | 否 |
| `该课程已开始，无法预约` | `❌ 该课程已开始上课，暂不接受预约...` | 否（"，无法预约" vs "上课，暂不接受预约"） |
| `只能预约未来两周内的课程` | `❌ 可预约范围仅限未来两周...` | 否 |
| `预约已取消` | `❌ 该预约已被取消...` | 否（"已取消" vs "已被取消"） |
| `当前预约状态无法签到` | `❌ 当前预约状态无法执行该操作...` | 否 |
| `未知...SQL: SELECT * FROM` | `⚠️ 操作失败，请稍后重试或联系客服` | 否 |

## 5. 静态结论

| AC | 判定 |
|----|------|
| AC-4.1 变更范围 ⊆ 白名单 2 文件 | ✅ PASS |
| AC-4.2 无契约变更 | ✅ PASS |
| AC-4.3 py_compile | ✅ PASS |
| AC-4.4 diff 仅触及目标方法 + 测试函数 | ✅ PASS |
