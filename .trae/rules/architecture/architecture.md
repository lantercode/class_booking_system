---
alwaysApply: true
---

# 系统整体架构

## 仓库形态

pnpm monorepo（`pnpm-workspace.yaml`：`apps/*` + `packages/*`）：

| 组件 | 路径 | 职责 |
|------|------|------|
| 后端 API | `apps/api` | FastAPI，唯一数据出入口，`/api/v1` 前缀 |
| 管理端 | `apps/admin-web` | Vue3 Web（Element Plus） |
| 学员端 | `apps/student-web` | Vue3 Web（Element Plus） |
| 教师端 | `apps/teacher-web` | Vue3 Web（Element Plus） |
| 小程序 | `apps/miniapp` | uni-app → 微信小程序（学员/教师双角色） |
| 共享包 | `packages/api-client`、`packages/api-types` | Web 三端 HTTP 客户端、OpenAPI 生成类型 |

## 系统边界（不可违反）

1. **前端（含小程序）只能通过 HTTP API 访问后端**，禁止直连 PostgreSQL / Redis，禁止在前端执行 SQL 或复制后端业务规则作为最终校验。
2. **后端是业务规则的唯一权威方**：容量、权限、租户、课时余额、状态机等核心规则只在 Service 层实现；前端校验仅用于交互体验。
3. **AI / MCP 是后端内部能力**，对外只暴露 `POST /api/v1/ai/chat` 等 HTTP 接口；MCP Server（FastMCP stdio）不直接暴露网络。
4. 跨模块复用业务能力时**调用对方模块的 Service**（如 booking 调用 membership_card_service），禁止直接写其他模块的 Repository / 表。
5. 全项目只允许两套 HTTP 客户端实现：Web 三端用 `packages/api-client`，小程序用 `apps/miniapp/src/api/index.ts`；不得新增第三套请求层。

## 模块职责

后端业务代码位于 `apps/api/src/app/modules/<name>/`，每模块固定四件套：`router.py`（接口）、`service.py`（业务与事务）、`repository.py`（数据访问）、`schemas.py`（DTO），模型在 `models.py`。分层细则见 `architecture/layering.md`。

AI 能力位于 `apps/api/src/app/ai/`，HTTP 出口在 `modules/ai/router.py`，边界细则见 `ai/ai-architecture.md` 与 `ai/mcp.md`。
