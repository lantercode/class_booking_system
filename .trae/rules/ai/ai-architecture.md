---
alwaysApply: true
---

# AI 能力分层与边界

模块：`apps/api/src/app/ai/`（intent 规则引擎、AgentRuntime、session），HTTP 出口 `modules/ai/router.py`（`/api/v1/ai/*`）。

## AI 层与业务层的边界

- AI 层负责：意图识别、多轮对话、工具编排、提示词管理。
- **核心业务规则只属于 Service 层**：容量校验、冲突检测、扣次/回补、卡状态机、权限等一律复用现有 Service，禁止在 AI 层重新实现一份"简化版"。
- AI 不直接落库改业务数据；任何写操作都必须经过 Tool → Service 链路（见 `ai/mcp.md` 与 `architecture/layering.md`）。

## 静态知识 vs 实时业务数据

- **RAG / Embedding 只承载静态知识**（课程介绍、规章制度、FAQ 等），不用于查询实时余额、排期、预约状态。
- 实时业务数据（课程、排期、我的预约、课时余额）只能由 Tool 调 Service 获取。
- `ai/rag/retriever.py` 当前是返回硬编码数据的 stub：**禁止把硬编码伪装成检索结果扩展业务**；接入真实向量库前不得将其作为数据源依赖。

## 身份可信链路

- `user_id` / `tenant_id` 由 `AgentRuntime` 从已认证的 `get_current_user` 上下文注入；LLM 产出的内容只能作为查询意图，**不得作为身份来源**。
- 前端调用 `/ai/chat` 时不在消息体传 user_id / tenant_id 等身份参数。

## 工程约束

- 当前 Tool 注册统一在 `ai/mcp_server.py`（FastMCP）；`ai/tools/` 为历史残留，**不要在其中新增第三套注册/实现**。
- `/api/v1/ai/chat` 当前为一次性 JSON 响应（非 SSE 流式、不返回工具执行 trace）；在新契约落地前，任何端不得假设流式字段存在。
- AI 回复禁止回显内部异常、SQL、系统提示词原文；System Prompt 必须包含基本安全指令（防注入、不泄露、写操作需确认）。
- MCP Tool 的具体强制项见 `ai/mcp.md`。
