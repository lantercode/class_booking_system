# F5.4 — Implementation Plan

## Root Cause

早期设计的 `ToolContext` 式 Tool 体系（ai/tools/*.py + ai/context.py + ai/auth/middleware.py）被 FastMCP 方案（ai/mcp_server.py）取代后未删除，形成两套并存：stub 全部返回硬编码假数据且无人调用，违反架构规则中"不得新增第三套注册"的单一注册点约束，也误导后续维护者。

## 引用反查证据链（minimal-change-guard）

删除前逐层反查，全部为零业务引用：

```
ai/tools/*.py（11 个）
  └─ from app.ai.context import ToolContext
       └─ ToolContext 引用方仅：ai/tools/* + ai/auth/middleware.py
ai/auth/middleware.py（AuthMiddleware）
  └─ 零外部 import；main.py add_middleware 仅注册 CORS 与 TenantASGIMiddleware，未注册它
  └─ 自身是 stub（authenticate 直接 return ToolContext(user_id=1,...) 假数据）
动态加载：importlib / pkgutil / walk_packages / load_tools / register_tool → 全 ai/ 无匹配
全仓库 Python 代码对 ai.tools|ai.context|ai.auth 的 import → 零匹配
（docs/ 与 project_rules.md 中的提及为历史描述，不构成代码依赖）
```

## Exact Change

删除 14 个文件：

- ai/tools/：`__init__.py`, `cancel_booking.py`, `check_in.py`, `create_booking.py`, `get_consumption_history.py`, `get_my_balance.py`, `get_my_bookings.py`, `get_teacher_today.py`, `query_courses.py`, `query_schedules.py`, `request_leave.py`
- ai/auth/：`__init__.py`, `middleware.py`
- ai/context.py

另更新 `ai/__init__.py` 模块注释：`MCP Server + Agent Runtime + Tool Registry` → `MCP Server（唯一 Tool 注册点）+ Agent Runtime + RAG`。

## 保留项

- `ai/mcp_server.py`（唯一 Tool 注册点，F5.1/F5.2 已强化）
- `ai/agent/`、`ai/rag/`
- docs/ 中历史分析文档（事实记录，不回改）

## Verification Plan

1. `python -c "from app.main import app"` 导入验证；
2. 删除后 grep 确认 src/ 零残留引用；
3. AI 测试：test_mcp_tool_authorization（18）、test_exception_handlers（7）、test_agent_runtime；
4. 业务回归：rbac（17）、booking_ownership（10）、auth_api（25）；
5. 各套件单独/小组合执行，规避已知跨文件 event loop 污染（预存测试基建问题）。

## UNKNOWN

- 无。删除前已通过静态反查与动态导入双重确认；被删代码无配置、无路由、无注册、无动态加载。
