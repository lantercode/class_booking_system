# F5.4 — Acceptance Criteria

| ID | 验收标准 | 验证方式 | 结果 |
|----|---------|---------|------|
| AC-1 | 全局无任何 `ai.tools` / `ai.context` / `ai.auth` / `ToolContext` 的 Python 引用 | 删除后 grep `src/ --include=*.py` 零匹配 | PASS |
| AC-2 | `ai/tools/` 目录（11 stub + __init__）已删除 | LS 目录不存在 | PASS |
| AC-3 | 连带孤儿 `ai/context.py`、`ai/auth/` 已删除 | LS 确认 | PASS |
| AC-4 | mcp_server.py 仍是唯一 Tool 注册点，6 个 Tool 完好 | LS ai/ 目录 + import 检查 | PASS |
| AC-5 | 应用可正常导入（无 ImportError / 循环引用） | `python -c "from app.main import app"` → IMPORT_OK | PASS |
| AC-6 | AI 授权测试 18/18 通过（F5.2 四关校验不受影响） | pytest test_mcp_tool_authorization.py | PASS |
| AC-7 | AI 异常处理测试通过（F1.3 + F5.3） | pytest test_exception_handlers.py + test_business_error_handling | PASS |
| AC-8 | 核心业务回归通过（RBAC 17 / 预约归属 10 / auth_api） | 各套件单独执行 | PASS |
| AC-9 | 无动态加载/反射注册机制引用被删模块（importlib/pkgutil/walk_packages） | 删除前 grep 无匹配 | PASS |
| AC-10 | rag/ 子系统不受影响 | grep 无牵连 + import 通过 | PASS |
