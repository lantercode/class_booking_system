# F5.4 — Review

## Scope Review

- 严格限定为删除零引用死代码：14 个文件删除 + 1 行注释更新；
- 未夹带任何功能修改、重构、格式化；
- 未触碰测试、DB、配置、前端。

## 删除安全性审查（minimal-change-guard）

| 检查 | 结论 |
|------|------|
| 静态 import 反查（全仓库 *.py） | 零引用 |
| 动态加载反查（importlib/pkgutil/反射注册） | 无机制 |
| main.py 中间件链 | AuthMiddleware 从未注册 |
| 被删代码性质 | 全部 stub（硬编码假返回 + TODO），无独有业务逻辑 |
| 删除后导入 | from app.main import app 成功 |
| rag/ 牵连 | 无 |

连本带利删除 `context.py` 与 `ai/auth/` 的合理性：二者仅服务于被删的 ToolContext 旧体系；保留它们会产生无入口孤儿代码，与本 Feature"消除两套并存"目标一致，且引用证据完整。

## Architecture Review

对照 `.trae/rules/ai/ai-architecture.md`：

- 删除后 Tool 注册唯一存在于 `ai/mcp_server.py`（FastMCP），规则中的事实状态从"残留待清理"变为"已合规"；
- HTTP → AgentRuntime → Tool → Service → Repository → DB 链路无断点；
- MCP 不暴露网络端口的约束不受影响（stdio）。

## Regression Review

- 隔离执行：rbac 17/17、F5.2+F1.3 25/25；
- 混排 79 绿；3 个异常均为预存（2 个 F5.1 数据依赖、1 个 event loop 测试基建问题，单跑全绿），与删除无因果；
- 无任何与 ai.tools/ai.context/ai.auth 相关的 ImportError。

## Risks

| 风险 | 等级 | 评估 |
|------|------|------|
| 外部脚本/仓库外代码引用被删模块 | 低 | 仓库内全量 grep 零引用；这些是 app 内部模块（非公共 API），不对外发布 |
| 被删 stub 中的独有 Tool（check_in/request_leave/get_teacher_today/get_consumption_history）未来需要 | 低 | 均为假数据无实现；未来需要时按 mcp.md 四关规范在 mcp_server.py 重新实现为真实 Tool（走 Service），恢复 stub 没有价值 |
| event loop 混跑错误被误判为回归 | 低 | 已用单跑 17/17 与 F5.2 历史记录双重排除 |

## New Tech Debt

无新增。既有的 D-F5.2-2（F5.1 脚本测试改造）与跨文件 event loop 隔离问题仍在 backlog，均非本 Feature 引入。

## Recommendation

**READY_FOR_ACCEPTANCE**

Epic 5（F5.1 / F5.2 / F5.3 / F5.4）全部关闭，AI 层架构规则（单一 Tool 注册、四关校验、异常不泄露、多轮链路可用）已全部落地。
