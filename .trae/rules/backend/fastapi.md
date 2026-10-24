---
alwaysApply: false
globs: "apps/api/**/*.py"
---

# FastAPI / 异步后端规范

适用：`apps/api`（Python 3.12，FastAPI + SQLAlchemy 2.0 Async + asyncpg + aioredis）。

## 异步与会话

- 全部数据库 IO 使用 `AsyncSession`；**禁止**使用同步 `Session`、裸 `psycopg2` 或阻塞式驱动。
- 请求链路的 DB 会话通过依赖注入获取（`db: AsyncSession`）；禁止在 Router/Service 内自行 `async with SessionLocal()` 开独立会话（中间件、定时任务等基础设施场景除外，且必须自管租户上下文）。
- 保持 `async/await` 链路完整；禁止在 async 代码中调用阻塞 IO（`requests`、同步文件长操作等）。

## 分层与依赖注入

- 遵守 Router → Service → Repository（见 `architecture/layering.md`）。
- Router 通过 `Depends(...)` 注入 DB、当前用户、Redis、RBAC 依赖；Service / Repository 不在 Router 之外被 HTTP 直接触达。
- 请求参数必须由 Pydantic 模型（`schemas.py`）校验；禁止在 Router 用手写 `if/else` 替代模型校验。

## 异常处理

- 业务异常抛 `DanceSaasException`（或 `HTTPException`），由全局 handler 统一转为 `{code,msg,data}` 信封；分层规则见 `architecture/layering.md`，信封见 `architecture/contracts.md`。
- **禁止向客户端泄露 traceback、内部 SQL、内部地址、密钥**；未知异常返回标准化的"服务暂时不可用"。
- 数据库完整性错误（如 `IntegrityError`）由全局异常处理器统一转换为业务错误，不向用户暴露原始约束名。

## 其他强制项

- 上传文件大小上限 2MB（复用 `common/upload/image` 既有实现）。
- 定时任务（APScheduler）在独立线程运行：自建 `SessionLocal()` 会话，且必须按租户循环手动 `set_tenant_id(...)`（见 `security/tenant-isolation.md`）。
- 多写操作的事务规则（`auto_commit=False`、行锁）见 `database/transaction.md`，不得在本层自行发明提交时机。
- AI 相关后端代码额外遵守 `ai/ai-architecture.md` 与 `ai/mcp.md`。
