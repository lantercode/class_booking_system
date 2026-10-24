# F5.1 — Release Note

> Feature：多轮预约流程修复
> 发布类型：缺陷修复（Defect Fix）
> 影响面：AI 对话预约链路

## 修复内容

修复 AI 多轮预约流程卡死的问题。根因是 `query_schedules` 工具的输出格式与运行时 `_parse_schedules` 的解析格式不匹配，导致排期永远解析为空，用户无法选择排期完成预约。

### 主要变更

1. **统一排期输出格式**：`query_schedules` 现输出 `- ID:{id} | {YYYY-MM-DD} | {HH:MM-HH:MM} | {教师} | 剩余:{名额} | {课程名}`，与解析端严格一致。
2. **解析端适配**：`_parse_schedules` 正则支持解析课程名，展示与预约成功回显均使用真实课程名。
3. **意图识别配套**：支持裸"预约"触发预约意图（如"预约明天的瑜伽课"），同时"可以预约"仍作为查询意图；预约意图可提取日期参数。

## 用户可感知变化

- 学员说"预约明天的瑜伽课"后，AI 会列出可选排期，回复序号即可完成预约。
- 查排期结果展示更结构化（含剩余名额）。

## 兼容性

- 后端 OpenAPI 契约无变化，`/api/v1/ai/chat` 请求/响应不变。
- 前端 4 端无需改动。
- Service 层无改动，预约业务规则（容量、冲突、扣次）不变。

## 验证

- 单元测试：`_parse_schedules` 对统一格式的 round-trip 解析。
- 端到端模拟："预约明天的瑜伽课"→ 选"1"→ 预约成功。
- 静态校验：全部修改文件 `py_compile` 通过；架构边界审查通过。

## 回滚

如需回滚，恢复以下 4 个文件至修改前版本即可：
- `apps/api/src/app/ai/mcp_server.py`
- `apps/api/src/app/ai/agent/runtime.py`
- `apps/api/src/app/ai/agent/intent.py`
- `apps/api/tests/test_agent_runtime.py`
