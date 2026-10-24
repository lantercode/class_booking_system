---
alwaysApply: true
---

# 分层与调用关系

## 标准调用链

```
Router → Service → Repository → SQLAlchemy → PostgreSQL
```

### Router 层

只允许做：参数提取与 Pydantic 校验、依赖注入（DB / 当前用户 / Redis）、调用 Service、返回响应。

- 禁止在 Router 内实现业务判断、状态流转、金额/课时计算。
- 禁止在 Router 内直接拼 SQL 查询条件或操作 ORM 模型查询；查询必须下沉到 Repository。
- 禁止用手写 `if/else` 校验替代 Pydantic 模型。

### Service 层

- 承载全部业务规则、状态机校验、事务边界（见 `database/transaction.md`）。
- 同一业务流程的多个写操作共享同一个 `AsyncSession`，由 Service 统一提交。
- 跨模块复用只能调用其他模块的 Service，不直接操作其 Repository。

### Repository 层

- 承载数据访问；持有租户数据的 Repository 必须继承 `TenantAwareRepository`（见 `security/tenant-isolation.md`）。
- 返回 ORM 实体或标量结果，不在 Repository 内做业务决策。

## AI / MCP 分层（同等强制）

```
HTTP /ai/chat → AgentRuntime → MCP Tool / 函数 → Service → Repository → DB
```

- MCP Tool / AI 运行时**只能调用 Service**，禁止直接访问 Repository、禁止裸 SQL、禁止直接操作 Redis 完成业务写入。
- AI 不拥有核心业务规则：预约冲突、扣次、冻结/解冻等判断一律复用现有 Service，不在 AI 层重新实现。
- Tool 自身的四关校验（鉴权/授权/租户/入参）见 `ai/mcp.md`。

## 禁止的跨层路径

- Router → DB（绕过 Service/Repository）
- MCP Tool / AgentRuntime → Repository / DB（绕过 Service）
- 前端 → DB / Redis（绕过 HTTP API）
- 定时任务绕过 Service 直接改写业务状态（任务内同样走 Service/Repository，并补齐租户上下文）
