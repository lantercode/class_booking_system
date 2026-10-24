# F5.4 — 清理 ai/tools/ 残留 · Requirement

## 背景

AI 模块长期存在两套 Tool 实现：

1. **生效路径**：`ai/mcp_server.py`（FastMCP 注册 6 个 Tool），由 `ai/agent/runtime.py` 直接 import 调用，由 `/api/v1/ai/chat` 驱动；
2. **历史残留**：`ai/tools/` 目录 11 个 stub 文件，基于 `ai/context.py` 的 `ToolContext` 体系，全部返回硬编码假数据（如 `return {"success": True, "booking_id": 1002}`）。

`.trae/rules/ai/ai-architecture.md` 已明确："当前 Tool 注册统一在 ai/mcp_server.py（FastMCP）；ai/tools/ 为历史残留，不要在其中新增第三套注册/实现。"

## Goal

消除两套 Tool 并存，删除未被引用的 stub 体系，使 mcp_server.py 成为唯一 Tool 注册路径。

## Scope

删除（均为零引用死代码）：

- `ai/tools/`：11 个 stub 文件 + `__init__.py`；
- `ai/context.py`：`ToolContext`，仅被 tools/ 与 ai/auth/ 引用；
- `ai/auth/`：`middleware.py`（返回硬编码假身份的 AuthMiddleware stub，未在 main.py 注册）+ `__init__.py`。

`ai/auth/` 与 `ai/context.py` 属于同一旧 stub 体系的连带孤儿：删除 tools/ 后 ToolContext 的唯一使用者只剩同样零引用的 AuthMiddleware，一并清理避免留下更隐蔽的孤儿。

## Out of Scope

- mcp_server.py / runtime.py 的任何功能改动；
- rag/ 目录（独立子系统，无牵连）；
- 文档（docs/）中对历史残留的描述性文字（属于历史记录，不回改）。
