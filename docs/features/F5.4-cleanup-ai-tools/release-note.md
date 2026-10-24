# F5.4 — Release Note

## 概述

清理 AI 模块的历史 Tool stub 体系，`mcp_server.py`（FastMCP）成为唯一的 Tool 注册与实现位置。

## 变更内容

删除 14 个无引用文件：

- `app/ai/tools/` 整个目录（11 个返回硬编码假数据的 Tool stub + __init__）；
- `app/ai/auth/` 整个目录（未注册的 AuthMiddleware stub + __init__）；
- `app/ai/context.py`（仅被上述旧体系使用的 ToolContext）。

另更新 `app/ai/__init__.py` 一行模块注释。

## 用户与接口影响

- **无任何运行时行为变化**：被删代码从未被运行时调用，AI 预约/取消/查询链路完全不受影响；
- 无 HTTP 契约变更、无数据库变更、无配置变更；
- 前端 4 端零改动，无需重新生成 api-types。

## 工程收益

- 消除"两套 Tool 并存"的维护歧义，后续 AI Tool 一律在 mcp_server.py 按四关规范实现；
- 移除可能误导开发者的假数据 stub（避免有人误接 stub 得到永远成功的假响应）。

## 验证

- 应用导入冒烟通过；
- 删除后全仓库 Python 代码零残留引用；
- RBAC 17/17、Tool 授权 18/18、异常处理 7/7、预约归属 10/10 等回归通过；
- 3 个混跑异常均为预存测试基建/数据依赖问题（隔离执行全绿），与本次删除无关。

## 部署注意

- 纯代码删除，随后端正常发布，无数据迁移与开关。
