# 项目分析与简历项目经历（基于仓库代码）

注：以下所有结论均基于仓库代码与配置文件（apps、infra、.github/workflows、README 等），未添加任何未实现或无法从代码中证实的数据。

---

## 一、项目整体架构（事实摘要）

- 前端技术栈：Vue 3、Vite、TypeScript、Element Plus、Pinia；包含三套前端：admin-web（管理后台）、student-web（学员端）、teacher-web（教师端），以及 miniapp（uni-app → 微信小程序）。证据：README、apps/miniapp、apps/admin-web 等目录。
- 后端技术栈：Python 3.12、FastAPI、SQLAlchemy 2.0（async）、Alembic。证据：apps/api/src/app、pyproject.toml、alembic。
- 数据库：PostgreSQL（Docker Compose 中使用 postgres:15，alembic 配置存在）。证据：infra/docker/docker-compose.yml、models/*.py。
- 缓存/会话：Redis（redis:7，项目在启动 lifespan 中明确依赖 Redis 并初始化）。证据：infra/docker/docker-compose.yml、get_redis_client、Agent SessionManager 使用 Redis。
- 消息队列：仓库内没有消息队列（如 RabbitMQ/Kafka）相关代码或配置——未使用。
- AI / LLM / RAG 组件：有自研 AI Agent 框架（FastMCP、AgentRuntime、IntentRecognizer、MCP Tools、SessionManager），实现了多轮对话、Tool 调用、基于规则的意图识别与 Redis 会话管理。RAG/Embedding 有框架（embedder.py、retriever.py）但 Embedding 与 Milvus 调用尚为 TODO（代码中有注释和占位返回）。证据：apps/api/src/app/ai/*。
- 容器化/编排：Docker + Docker Compose（infra/docker/docker-compose.yml 与 docker-compose.prod.yml），api 有 Dockerfile。证据：infra/docker、apps/api/Dockerfile。
- 反向代理：Nginx 配置用于部署（deploy workflow 中拷贝 infra/nginx/nginx.conf 并 reload）。证据：.github/workflows/deploy.yml。
- CI/CD：GitHub Actions（ci.yml 做 lint/test/build；deploy.yml 做 SSH 部署到 ECS + Docker Compose 部署）。证据：.github/workflows/*。
- 第三方服务/集成：计划接入 OpenAI embeddings（embedder.py 注释），并使用 Milvus 作为向量存储（retriever.py 注释），但目前是占位实现；另外部署脚本使用 SSH 到 ECS。证据：apps/api/src/app/ai/rag/*.py、.github/workflows/deploy.yml。
- 部署方式：可以通过 Docker Compose 在服务器上部署（infra/docker/docker-compose.prod.yml），并在 CI/CD 中通过 SSH 执行构建、替换 Nginx 配置、启动容器、运行 Alembic 迁移与健康检查。证据：deploy.yml、infra/docker/*。

---

## 二、业务层面分析（代码证据驱动）

- 项目要解决的问题：为舞蹈机构提供多租户的约课系统，覆盖学员预约、教师排期、管理后台运营与微信小程序入口。证据：README 功能列表、modules 目录（course、schedule、booking、user、teacher、classroom、tenant）。
- 目标用户：舞蹈机构（租户）以及其学员、教师与管理员。证据：Tenant 模型、多租户中间件、前端有三端（学员/教师/管理）。
- 核心业务流程：课程 → 创建排期（CourseSchedule）→ 学员预约（Booking）→ 取消/签到/完成；管理后台管理课程/教师/教室/排期；AI 助手用于用自然语言查询/预约/取消。证据：models、service、router、mcp_server 工具（query/create/cancel）。
- 核心模块：auth（JWT）、user、role（RBAC）、course、schedule、booking、ai（agent）、tenant、admin。证据：app/modules/*.py。
- 用户角色：学员（student）、教师（teacher）、管理员（admin/role 模块），并用 RBAC 管理权限（app/core/rbac 存在）。
- 体现复杂工程的功能：
  - 多租户支持（tenant middleware + SQLAlchemy 查询注入）——防止跨租户数据泄露。
  - 分层 API 设计（router → service → repository/ORM models）。
  - 异步后端（SQLAlchemy async session、FastAPI async handlers）。
  - AI Agent：多轮状态管理、Tool 调度、分布式锁防重复预约、友好错误映射。
  - CI/CD 与生产部署脚本（健康检查、镜像构建、迁移与回滚流程）。

---

## 三、从代码可写进简历的技术亮点（按维度）

（下列点均有代码证据）

前端（可以在简历中简短提及）
- 多端工程：构建了 Admin/Student/Teacher 三套 Web 前端与 uni-app 小程序端，使用 Vue3 + TypeScript + Pinia + Element Plus + Vite；抽取共享 packages（api-client、api-types、shared-ui）。证据：apps/*、packages/*。

后端（重点亮点）
- 使用 FastAPI + SQLAlchemy(2.0 async) 构建异步 REST API，统一 DB 会话由 async_sessionmaker 管理。证据：app/core/database.py、routers。
- 实现 JWT 双 Token（access + refresh）与 Redis 黑名单机制。证据：app/core/security.py、get_redis_client、token 黑名单函数。
- 分层架构（router → service → repository），以及自定义异常与响应封装（app/core/response.py、exceptions、middleware/error_handler.py）。证据：modules/* / service 文件存在。
- RBAC 权限体系与基于 ContextVar 的租户/用户/角色注入（tenant_middleware、tenant_query、deps/auth）。证据：tenant_middleware.py、tenant_query.py、deps/auth.py。
- 多租户自动注入：使用 SQLAlchemy Session do_orm_execute 事件，自动为带 tenant_id 的实体注入 WHERE 条件，降低开发者失误导致的数据泄露风险。证据：app/core/tenant_query.py。

数据库
- PostgreSQL + SQLAlchemy，表设计体现约束（CheckConstraint、唯一索引、部分索引、复合唯一索引带条件），并使用 Alembic 管理迁移。证据：models.py 中的 Index/CheckConstraint、alembic。
- 事务与约束：Booking 表使用 DB 级唯一索引（schedule_id + student_id 在 active 状态下唯一）以防重入。证据：uq_bookings_schedule_student_active 索引定义。

工程化 / 运维
- Docker Compose 本地/生产编排、健康检查、数据卷持久化；CI/CD 使用 GitHub Actions 做 lint/test/build 与远端 SSH 部署脚本（含镜像构建、迁移、Nginx 配置引用）。证据：infra/docker、.github/workflows/*。
- 生产就绪特性：服务健康检查、Redis 依赖检查、日志/错误处理与部署期间滚动替换容器流程。证据：main.py lifespan、deploy.yml 部署步骤。

AI / Agent
- 自研 AgentRuntime 与 FastMCP 工具集成，设计了 Tool 分类（查询/操作），并通过工具安全地调用后端业务 Service（create_booking、cancel_booking 等），实现自然语言 → 意图识别 → Tool 调度 → 业务执行的闭环。证据：app/ai/agent/runtime.py、mcp_server.py。
- 多轮对话管理：SessionManager 使用 Redis 保存历史与中间状态，支持选择排期的多轮交互与确认流程。证据：agent/session.py。
- 并发控制：对话层使用 Redis 分布式锁（SET NX EX + Lua 安全释放）防止重复预约。证据：AgentRuntime._acquire_lock / _release_lock。
- RAG 管线已规划（embedder.py 与 retriever.py），但向量化与 Milvus 集成目前为 TODO（代码中返回占位结果）。证据：app/ai/rag/embedder.py、retriever.py 注释。

---

## 四、可转化为简历亮点（示例句式）

亮点 1：系统架构
- 说明（简述）：基于 Vue3 + FastAPI 的多端多租户 SaaS，前端统一使用 pnpm monorepo 管理，后端采用异步 FastAPI + SQLAlchemy，容器化通过 Docker Compose 部署，CI/CD 用 GitHub Actions + SSH 自动化部署到 ECS，并通过 Nginx 负责反向代理与静态托管。
- 简历一句话：基于 Vue3 + FastAPI 构建多租户约课 SaaS，使用异步 SQLAlchemy 做数据层、Docker Compose 与 Nginx 做容器化部署，GitHub Actions 实现从构建到远端 SSH 自动部署流水线。

亮点 2：后端架构
- 说明：采用 router→service→repository 分层，使用 FastAPI 异步路由与 async SQLAlchemy 会话，统一异常/响应封装；实现 JWT 双令牌与 Redis 黑名单、RBAC 权限控制与 ContextVar 注入的多租户中间件。
- 简历一句话：设计并实现基于 FastAPI 的分层后端（router→service→repository），完成 JWT（含 refresh）与 RBAC、ContextVar 驱动的多租户中间件与 SQLAlchemy 查询注入，保障数据隔离与权限可审计。

亮点 3：数据库设计
- 说明：使用 PostgreSQL，模型层体现约束（时段冲突/容量、check constraint）、索引与条件唯一索引（防止重复预约），并用 Alembic 管理迁移。多租户通过在实体中包含 tenant_id 并采用 do_orm_execute 自动注入 WHERE 过滤实现隔离。
- 简历一句话：使用 SQLAlchemy + PostgreSQL 设计健全的业务模型（约束与索引），并实现 do_orm_execute 层面自动注入 tenant_id 策略以保证多租户数据隔离。

亮点 4：AI / Agent 能力
- 说明：实现了 AgentRuntime (多轮对话、意图识别、Tool 调度)、FastMCP Tool 集成（对业务 API 的安全封装）、Redis 会话与状态管理、并发锁防止重复预约；同时规划了 RAG（embedder/retriever）接入 OpenAI/Milvus 的路线，当前为占位实现。注意：Embedding 与 Milvus 的真实调用尚未完成。
- 简历一句话：构建企业级 AI Agent（IntentRecognizer + AgentRuntime + FastMCP Tools），实现自然语言到安全后端操作的闭环，多轮会话与 Redis 状态管理并采用分布式锁防止重复预约；同时规划 RAG 向量化与 Milvus 集成。

亮点 5：工程化 / DevOps
- 说明：完整 Docker Compose 本地/生产配置、服务健康检查与持久化卷，CI 做自动化 lint/test/build，deploy workflow 支持远端 SSH、构建镜像、运行迁移与 Nginx 部署，能将服务部署到 ECS 服务器。证据：infra/docker、.github/workflows/deploy.yml。
- 简历一句话：实现从 CI 到生产的完整部署流水线（GitHub Actions → SSH → Docker Compose），包含镜像构建、Alembic 迁移、Nginx 配置与健康检查，具备可上生产环境的部署能力。

---

## 五、资深面试官视角：你可能未注意到的亮点（代码层面）

1. 已体现的工程能力：
   - SQL 层面的约束设计（CheckConstraint、条件唯一索引）显示对一致性与重入问题的把控（尤其 bookings 的唯一索引防止重复预约）。
   - TenantQuery 的 do_orm_execute 注入是一个业界较好的多租户防护机制，能在框架层面防止开发失误。
   - Agent 的错误码到友好提示的映射体现了产品化思维（将技术错误映射为用户友好指引）。

2. 可包装成亮点的设计：
   - Redis 会话 + 状态机（SessionManager）可描述为“支持多轮事务性对话的状态管理”，是面试中容易深挖的点。
   - 使用 Lua 安全释放分布式锁可包装为并发控制与幂等设计。

3. 能体现从前端向后端转型的证据：
   - 参与设计 api-client、api-types 与前后端协作（OpenAPI → TS 类型），展示你理解前端需求并在后端提供契约化接口的能力。

4. AI Agent 工程能力点：
   - 完整实现了从 NL 意图识别（目前基于规则）到 Tool 调度和业务 Service 调用的工程链路；这是 AI 产品落地的关键。可被问及：如何保证安全、如何注入用户上下文、如何处理并发与事务。代码中都有实现。

5. 容易被追问的点（面试官常问）：
   - 多租户实现细节：tenant_id 如何注入、如何处理管理员跨租户查询？（代码展示了跳过/校验逻辑）
   - 并发控制与幂等性：Index 与分布式锁为何双重保障？如何保证 Lua 脚本安全性？
   - AI 安全与权限：Agent 调用 create_booking 时如何确保 user_id 是正确且有权限的？（AgentRuntime 通过 get_current_user 注入 user_id）
   - RAG 的实现细节：目前是占位，面试官可能追问 embedding pipeline 与向量检索的具体实现与评估方法。

6. 不值得写进简历或需要谨慎的地方：
   - embedder/retriever 目前为 TODO，不能宣称已完成 RAG 向量化。只能写为“规划与部分实现”。
   - 如果你没有参与到某个子模块（例如 admin-web 的全部页面），不要写成“独立负责全部前端页面”，建议使用“参与/负责若干关键模块”。

7. 建议补强（在写简历前或面试前准备）以便更有说服力：
   - 补齐 Embedding 与 Milvus/Chroma 的完整接入并写好端到端示例（问题→检索→生成→调用 Tool）。
   - 添加更多端到端集成测试（AI 接口 + 真实 DB 流程）以证明稳定性。

---

## 六、可直接放入简历的项目经历（三个定向版本）

### 公共头部
项目名称：Dance SaaS — 多租户舞蹈机构约课系统（全栈/AI Agent）
角色：全栈工程师 / AI Agent 应用开发
主要技术：Vue3, TypeScript, FastAPI, Python 3.12, SQLAlchemy(2.0 async), PostgreSQL, Redis, Docker, Nginx, GitHub Actions

---

### Version A：Python 后端工程师（面向后端岗位）
项目描述（2 行）：
- 为多租户舞蹈机构构建后端核心业务与管理后台 API，覆盖课程、排期、预约、用户与角色权限管理。
- 负责设计异步 FastAPI 服务、数据库模型、JWT + RBAC 认证、以及生产级部署流水线。

亮点（5 条）：
1. 基于 FastAPI + async SQLAlchemy 构建分层后端（router→service→repository），实现统一异常处理与响应封装，提升可维护性与测试覆盖。
2. 设计并实现 JWT（access/refresh）与 Redis 黑名单策略，保障会话安全并支持 token 旋转与强制登出。
3. 实现多租户隔离：通过 Tenant ASGI 中间件解析 x-tenant-id/slug 并在 SQLAlchemy do_orm_execute 层自动注入 tenant_id 筛选，防止跨租户数据泄露。
4. 在 DB 设计层使用 CheckConstraint、条件唯一索引与索引策略（如 bookings 的 schedule+student 有条件唯一索引）来保障业务幂等与一致性。
5. 搭建 CI（Lint/Test）与生产部署（SSH → Docker Compose → Alembic 迁移 → Nginx），使后端具备可上线的生产能力。

---

### Version B：AI Agent 应用工程师（面向 LLM/Agent 岗位）
项目描述（2 行）：
- 构建企业级 AI Agent 层，支持自然语言查询课程/排期与通过 Tool 安全地调用后端业务（预约/取消）。
- 实现多轮对话状态管理、意图识别、Tool 调度与并发控制，规划 RAG 向量检索方案。

亮点（5 条）：
1. 搭建 AgentRuntime + FastMCP 工具集成，将自然语言意图映射为查询/操作 Tool（例如 query_schedules、create_booking、cancel_booking），实现 LLM→Tool→业务 API 的桥接。
2. 实现多轮对话会话管理（SessionManager 使用 Redis 保存历史与中间状态），支持选排期并等待用户确认的交互式流程。
3. 设计并实现分布式锁（Redis SET NX EX + Lua 安全释放）以防止并发重复预约，兼顾可用性与安全性。
4. 规划 RAG 管线（embedder/retriever）以接入 OpenAI Embeddings 与 Milvus 做 FAQ/知识检索（当前为框架实现，Embedding 接入为后续任务）。
5. 将 Agent API（/api/v1/ai/chat）与业务鉴权/限流/日志对接，确保 AI 能在受控环境下安全访问业务系统。

---

### Version C：AI 全栈工程师（前后端 + AI）
项目描述（2 行）：
- 负责小程序与 Web 前端的部分实现与后端 AI Agent 的端到端对接，使学员可通过自然语言在小程序内完成课程查询与一键预约。
- 在前端实现 token 自动刷新、tenant header 注入与统一 API 客户端，并在后端实现 Agent 工程化与部署。

亮点（6 条）：
1. 在 uni-app 小程序与 Vue3 管理后台中实现统一的 API 客户端（packages/api-client），支持 token 自动刷新与 tenant header 注入，保障跨端一致的鉴权体验。
2. 将 AI Agent（/api/v1/ai/chat）接入小程序端，完成自然语言→意图→业务调用的端到端流程，实现小程序内的“语音/文本助手”交互。
3. 后端使用 FastAPI + async SQLAlchemy 提供高并发异步接口，Agent 层通过 Redis 会话管理多轮对话并保证并发安全。
4. 在 DB 层设计事务与约束（如预约唯一索引、排期容量校验）来保证业务正确性，前端通过合理交互降低冲突概率。
5. 参与 Docker Compose 与 CI/CD 流程，能把前后端与服务一起部署到 ECS + Nginx 环境。
6. 规划并开始实现 RAG/Embedding 管线，为后续增强型问答与知识检索奠定基础（embedder/retriever 已有框架）。

---

## 七、面试官视角评分与建议

评分（基于仓库代码可验证部分，满分 10）：
- 项目含金量：8/10（真实业务、完整栈、部署与 CI，可作为求职亮点）
- 后端能力：9/10（异步 FastAPI、SQLAlchemy 2.0、租户注入、JWT/Redis/索引设计等体现较高工程能力）
- AI Agent 能力：7/10（Agent 基础框架与多轮流程、Tool 调度与并发控制实现到位；RAG/Embedding 部分尚为占位）
- 工程化能力：8/10（Docker Compose、健康检查、CI/CD、远端部署脚本较为成熟）
- 全栈能力：8/10（多端前端、api-client、types 与后端契约对接体现全栈理解）

优势：该项目把传统业务（预约系统）与 AI Agent 工程化地结合起来，展示了你从前端向后端和 AI 方向过渡的能力；多租户与数据库约束设计体现工程成熟度。

短板：RAG/向量检索与 Embedding 仍为规划/占位，若面试官要求真实的向量检索工程经验需要补齐。

下一步最值得补的 5 个功能/技术点（优先级排序）：
1. 完整接入 Embedding（OpenAI 或本地模型）并把向量写入 Milvus/Chroma，完成端到端 RAG 示例。
2. 为 AI Agent 增加 LLM 语义解析的 fallback（例如将规则识别与 LLM 结合以提升 NLU 覆盖率），并加入安全策略与审计日志。
3. 增加端到端集成测试（包括 AI → Tool → DB 的流程），并在 CI 中加入关键场景的回归测试。
4. 丰富监控与指标（API latency、AI latency、错误率、队列长度等），在部署脚本中引入 Prometheus 或日志收集管道。
5. 完善幂等策略与并发压力测试（验证索引 + 分布式锁在高并发下的表现），并记录测试结果。

---

## 文件保存
此分析已保存到本仓库：project_experience.md

---

如果需要，我可以：
- 根据你求职的具体岗位（把上面的 Version A/B/C 进一步精简为一段可复制粘贴进简历的条目）；
- 或者把某些亮点扩写成面试回答要点与可能被问到的细节问答清单（每条 2–4 个追问与示例回答）。

请选择下一步。

---

附录：精简版简历条目（单段，可直接粘贴）

Version A（Python 后端工程师）: 基于 FastAPI + async SQLAlchemy 构建多租户后台服务，设计 JWT（access/refresh）与 Redis 黑名单、实现 router→service→repository 分层、用 SQLAlchemy do_orm_execute 自动注入 tenant_id 保证数据隔离，并通过 Docker Compose + GitHub Actions + SSH 自动化部署到 ECS（含 Alembic 迁移与 Nginx 配置）。

Version B（AI Agent 应用工程师）: 构建 AgentRuntime + FastMCP 工具集成，实现自然语言→意图→Tool 调度到后端业务的闭环，使用 Redis 管理多轮会话与中间状态，采用分布式锁防并发重复预约，并规划 RAG pipeline（Embedding→Milvus）用于知识检索。

Version C（AI 全栈工程师）: 负责小程序与 Web 前端的 API 客户端（token 自动刷新与 tenant 注入）并对接后端 Agent，实现小程序端的自然语言助手；后端采用 FastAPI 异步接口、Redis 会话与分布式锁，整体以 Docker Compose + CI/CD 部署到生产环境。

---

附录：面试问答清单（面试官可能提问 + 建议要点）

1) 多租户如何实现的？
要点：TenantASGIMiddleware 从 header 提取 x-tenant-id/slug 设置 ContextVar；SQLAlchemy do_orm_execute 自动注入 tenant_id 过滤；重要性：在框架层面防止跨租户泄露。

2) 为什么要在 ORM 层注入租户过滤，而不是每个查询手动加？
要点：减少人为错误、一致性、可集中审计；实现方式：with_loader_criteria + do_orm_execute 事件。

3) 预约并发冲突如何保障幂等？
要点：DB 层条件唯一索引防止重复插入（uq_bookings_schedule_student_active），业务层用 Redis 分布式锁（SET NX EX + Lua 安全释放）双重保障。

4) 分布式锁为什么用 Lua 脚本释放？有什么风险？
要点：避免误删他人锁（检查值再 DEL），风险：锁超时与异常处理，建议使用随机 token 验证持有者。

5) JWT token 黑名单如何工作？为什么需要？
要点：refresh token 被撤销或强制登出时将 jti 存 Redis blacklist，校验时查询 Redis；用于即时失效而非仅依赖 exp。

6) AI Agent 是如何安全调用后端业务的？
要点：Agent 只调用已注册的 Tool（封装在 mcp_server），Tool 内部通过 service 层执行带鉴权的业务逻辑；AgentRuntime 获取 current_user 后传 user_id 给 Tool。

7) RAG 部分目前有哪些准备工作？现在缺什么？
要点：已实现 embedder/retriever 框架，TODO 是接入实际 Embedding API 与 Milvus/Chroma，并编写索引/检索与 rerank 流程。

8) Agent 的多轮会话如何持久化？如何避免状态混淆？
要点：SessionManager 在 Redis 保存 history 与 state（带 TTL），session_id 隔离不同会话，操作完成后 clear_state。

9) 如何在 CI 保证数据库迁移安全执行？
要点：在部署脚本中先构建镜像、启动容器、再执行 alembic upgrade head，并在健康检查与日志失败时回滚或阻断部署。

10) 如果要求进行高并发压测，你会重点验证什么？
要点：预约并发冲突（重放客户端请求）、锁性能（Redis）、DB 索引与事务等待、延迟与超时策略、以及监控指标。

11) 如何评估并选择向量数据库（Milvus vs Chroma）？
要点：考虑吞吐/延迟、部署复杂度、可扩展性、社区与持久化、与现有 infra 的兼容性；先做 PoC 验证检索质量与成本。

12) 面试官可能要求你现场修改 AI Agent 行为，会被问到哪些点？
要点：如何增加新 Intent（intent.py）、如何注册新 Tool（mcp_server.py @mcp.tool）、如何确保 Tool 的安全边界与输入校验。


---

以上已追加到本文件。如需把其中任一单段条目再压缩为一句话（用于简历行），或把 Q&A 转成可打印面试卡片，回复我即可。

---

单行简历条目（可直接用于简历）

Version A（后端工程师）: 基于 FastAPI + async SQLAlchemy 构建多租户后台服务，使用 JWT（access/refresh）与 Redis 黑名单、在 ORM 层通过 do_orm_execute 自动注入 tenant_id 保证数据隔离，并通过 Docker Compose + GitHub Actions 自动部署（含 Alembic 迁移）。

Version B（AI Agent 应用工程师）: 实现 AgentRuntime + FastMCP 工具链（自然语言→意图→Tool→业务），用 Redis 管理多轮会话并存中间状态，采用 Redis 分布式锁保障并发幂等，规划 RAG（Embedding→Milvus）用于知识检索。

Version C（AI 全栈工程师）: 负责前端 API 客户端与小程序对接（token 自动刷新、tenant header 注入），并实现后端 AI Agent 与异步 API，使用 Redis 会话与分布式锁，整体以 Docker Compose + CI/CD 部署到生产环境。

---

可打印面试卡片（精简 Q&A）

1) 多租户如何实现的？ — TenantASGIMiddleware 从 header 提取 x-tenant-id/slug 注入 ContextVar；SQLAlchemy do_orm_execute 事件在 ORM 层自动加 tenant_id 筛选，统一防止跨租户泄露。

2) 预约并发冲突如何保障幂等？ — 在 DB 层用条件唯一索引防止重复预约（uq_bookings_schedule_student_active），在业务/Agent 层用 Redis 分布式锁（SET NX EX + Lua 安全释放）双重保障。

3) Agent 调用后端如何保证安全？ — Agent 只调用注册的 Tool（mcp_server），Tool 通过 service 层执行并依赖 get_current_user 注入的 user_id 做权限校验。

4) RAG 目前是什么状态、下一步怎么做？ — 已搭建 embedder/retriever 框架，下一步接入 Embedding API（如 OpenAI）并写入 Milvus/Chroma，完成索引/检索/重排流程并评估质量。

5) 为什么用 Lua 脚本释放锁？有什么风险？ — Lua 脚本保证检查持有者再删除的原子性，避免误删他人锁；风险包括锁超时、需要 token 验证以防误删。

6) JWT 黑名单如何工作？ — 将被撤销或登出时的 token jti 写入 Redis blacklist，校验时查 Redis 实现即时失效。

7) CI 部署如何保证数据库迁移安全？ — 部署脚本先构建镜像并启动容器，再在容器内运行 alembic upgrade head，结合健康检查与日志失败判断回滚或阻断发布。

8) 高并发压测你会关注哪些指标？ — 预约冲突率、Redis 锁命中与延迟、DB 事务等待/死锁、API 延迟/错误率、系统资源与监控告警阈值。

---

已追加并保存。
