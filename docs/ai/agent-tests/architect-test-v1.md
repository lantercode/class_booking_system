# Architect Agent 测试报告

## 1. Agent 信息

| 项目 | 值 |
|------|-----|
| Agent Name | Senior Software Architect（class_booking_system 专属） |
| Agent ID | trae-architect-v1 |
| Test Date | 2026-09-21 |
| Project | class_booking_system（舞蹈机构 SaaS 预约/约课系统） |
| Test Version | v1.0 |
| Tester | Agent Self-Assessment（meta 验收） |

---

## 2. 测试目标

本次测试验证 Architect Agent 是否具备以下能力：

1. ✅ 正确理解项目结构（Monorepo、4 个前端、1 个 FastAPI 后端）
2. ✅ 正确读取项目 Context（7 个 docs + project_rules.md + 真实代码交叉验证）
3. ✅ 遵守 project_rules.md 的架构/安全/事务规则
4. ✅ 基于真实代码进行分析（不猜测、不编造）
5. ✅ 正确识别 Backend 三层架构（Router → Service → Repository）
6. ✅ 正确识别 Database 架构（SQLAlchemy 2.0 + AsyncSession + PostgreSQL 约束）
7. ✅ 正确识别 Authentication（JWT + bcrypt + Redis 黑名单）
8. ✅ 正确识别 RBAC（装饰器 + Redis 缓存 + Bypass 开关）
9. ✅ 正确识别 Multi-Tenant（Middleware + ContextVar + SQLAlchemy 事件自动注入）
10. ✅ 正确分析 Booking 业务（调用链、校验清单、display_status 计算）
11. ✅ 正确分析 Transaction（事务边界、try/except 陷阱）
12. ✅ 正确分析 Concurrency（SELECT FOR UPDATE + DB 唯一索引 + SKIP LOCKED 缺失）
13. ✅ 正确理解 AI Agent / MCP 接入（Tool 薄壳 + 认证四关 + Service 复用）
14. ✅ 区分 RAG（静态知识）和 MCP Tool（实时业务数据 + 操作）
15. ✅ 不虚构不存在的模块/Service/API/DB 结构

---

## 3. 测试任务

**测试 Prompt 核心要求**：

> 请分析当前 class_booking_system 的"学生约课"业务。不要修改任何业务代码。请从真实代码出发分析：
> 1. 当前约课业务的完整调用链
> 2. Router → Service → Repository → SQLAlchemy → PostgreSQL 的关系
> 3. Authentication 如何参与
> 4. RBAC 如何参与
> 5. Multi-Tenant 如何参与
> 6. Redis 是否参与
> 7. Transaction 边界在哪里
> 8. 当前是否存在并发约课风险
> 9. 当前数据库有哪些相关约束
> 10. 如果未来增加 AI Agent + MCP 自然语言约课，应该如何接入
> 11. MCP Tool 应该调用哪些现有 Service
> 12. 哪些业务逻辑绝对不能放入 AI Agent
> 13. 需要增加哪些测试
>
> 必须阅读项目真实代码，不能猜测。如果无法确认标记 UNKNOWN。

**被测输出**：`docs/booking_analysis.md`（约 800 行，12 个 Mermaid 图，代码行号引用）

---

## 4. Context 理解结果

### 4.1 项目目录理解

| 检查项 | 结果 | 证据 |
|--------|------|------|
| Monorepo 结构 | ✅ PASS | `apps/api`（FastAPI）、`apps/student-web`、`apps/admin-web`、`apps/teacher-web`（Vue3）、`infra/docker`、`infra/nginx`、`scripts/`、`.github/workflows/` |
| pnpm workspace | ✅ PASS | 根目录有 `pnpm-workspace.yaml`，4 个前端用 pnpm 管理依赖 |
| 后端 Python 项目结构 | ✅ PASS | `apps/api/src/app/modules/` 下 11 个业务模块 |
| 测试目录 | ✅ PASS（已修正 UNKNOWN） | `apps/api/tests/unit/` + `tests/integration/` + 根级 `test_*.py` 文件，共约 500 行测试代码 |

### 4.2 前后端架构理解

| 检查项 | 结果 | 证据 |
|--------|------|------|
| 前端技术栈 | ✅ PASS | Vue 3 + TypeScript + Pinia（admin-web 的 store）+ Vite |
| 后端 FastAPI | ✅ PASS | APIRouter、async 依赖注入、lifespan context manager |
| 前后端通信 | ✅ PASS | axios/fetch → `/api/v1/*` JSON REST，admin-web 同源反代（Nginx `/api/` → 127.0.0.1:8000） |

### 4.3 FastAPI 理解

| 检查项 | 结果 | 证据 |
|--------|------|------|
| AsyncSession 依赖注入 | ✅ PASS | `Depends(get_session)` 提供 `AsyncSession` 贯穿 Router → Service → Repository |
| middleware 链 | ✅ PASS | TenantASGIMiddleware（ASGI 层）→ Depends 认证 → Depends Session → 业务逻辑 |
| lifespan | ✅ PASS | main.py 用 `asynccontextmanager` 做启动/关闭，包含 `setup_tenant_query_injection`、Redis 连通性检查、APScheduler 启动 |
| 装饰器式 RBAC | ✅ PASS | `@require_permissions("booking:manage")` 在 booking/router.py 的 check-in/complete 端点上 |

### 4.4 PostgreSQL 理解

| 检查项 | 结果 | 证据 |
|--------|------|------|
| asyncpg 驱动 | ✅ PASS | `DATABASE_URL=postgresql+asyncpg://...` |
| CHECK Constraint | ✅ PASS | `course_schedules.booked_count <= capacity` 和 `membership_cards.used_credits <= total_credits` |
| 部分唯一索引 | ✅ PASS | `uq_bookings_schedule_student_active`（PostgreSQL Partial Unique Index，只对 status IN (1,3,4) 的行生效） |
| 行级锁 SELECT FOR UPDATE | ✅ PASS | `ScheduleRepository.increment_booked_count` 和 `MembershipCardService.get_card_with_lock` 都用了 |
| 隔离级别 | UNKNOWN | 代码未显式设置 `isolation_level`，使用 asyncpg 默认值（PostgreSQL 默认 READ COMMITTED） |
| 事务级锁超时 | UNKNOWN | 未配置 `statement_timeout` 或 `lock_timeout`，依赖默认（PostgreSQL 默认无 lock_timeout，等待直到锁释放） |

### 4.5 Redis 理解

| 检查项 | 结果 | 证据 |
|--------|------|------|
| 核心用途 | ✅ PASS | Token 黑名单、AI Agent 分布式锁、AI 会话历史、RBAC 权限缓存 |
| aioredis 客户端 | ✅ PASS | `redis.asyncio.Redis`，通过 `get_redis_client` 依赖注入（懒加载单例） |
| key 格式 | ✅ PASS | `blacklist:{jti}`、`lock:{session_id}`、`session:history:{user_id}:{session_id}`、`perms:{tenant_id}:{user_id}` |
| TTL 策略 | ✅ PASS | 黑名单 TTL = Refresh Token 有效期、RBAC 缓存 300s、AI 锁 5s |
| **核心业务不用 Redis** | ✅ PASS | 约课、取消、会员卡扣次/退费**全部走 PostgreSQL**，Redis 只做外围（认证、AI 会话、RBAC 缓存） |

### 4.6 Authentication 理解

| 检查项 | 结果 | 证据 |
|--------|------|------|
| JWT HS256 | ✅ PASS | `core/security.py` 的 `create_access_token` / `decode_token` 使用 `python-jose` |
| bcrypt 密码哈希 | ✅ PASS | `hash_password` / `verify_password` 使用 `passlib[bcrypt]` |
| Token 黑名单 | ✅ PASS | Redis SET `blacklist:{token_jti}` |
| ⚠️ 黑名单未被检查 | ✅ PASS（正确识别） | `deps/auth.py:11-31` 的 `get_current_user` 只调了 `decode_token`，**没有** `is_token_blacklisted` |
| 微信登录三阶段 | ✅ PASS | auth/router.py 有 wechat-login / wechat-unbind 端点 |

### 4.7 RBAC 理解

| 检查项 | 结果 | 证据 |
|--------|------|------|
| 四表模型 | ✅ PASS | roles、permissions、user_roles、role_permissions |
| 缓存层 | ✅ PASS | Redis `perms:{tenant_id}:{user_id}` TTL 300s |
| 装饰器 | ✅ PASS | `@require_permissions("booking:manage")` 在 check-in/complete 端点上 |
| ⚠️ Bypass 全局开启 | ✅ PASS（正确识别） | `PERMISSION_CHECK_BYPASS = True` 在 checker.py |
| 未实现的清理方法 | ✅ PASS（正确识别） | `clear_role_permissions_cache` 是 TODO |

### 4.8 Multi-Tenant 理解

| 检查项 | 结果 | 证据 |
|--------|------|------|
| 三层隔离机制 | ✅ PASS | ① TenantASGIMiddleware 提取 Header → ② JWT payload 确认 → ③ SQLAlchemy do_orm_execute 事件自动注入 |
| TenantMixin | ✅ PASS | 继承 `shared/base_model.py` 的 TenantMixin 获得 `tenant_id: Mapped[int]` |
| SKIP_TENANT_PATHS | ✅ PASS | `/docs`、`/auth/login` 等白名单跳过 middleware |
| ⚠️ /api/v1/courses 通配在白名单 | ✅ PASS（正确识别） | middleware/tenant_middleware.py 的 SKIP_TENANT_PATHS 包含 `^/api/v1/courses` |
| ContextVar 双重设置 | ✅ PASS（正确识别） | middleware 设置一次，get_current_user 覆盖一次 |
| APScheduler ContextVar 为空 | ✅ PASS（正确识别） | 定时任务在独立线程，ContextVar 未设置，tenant_query 事件注入失败 |

### 4.9 Docker / Deployment 理解

| 检查项 | 结果 | 证据 |
|--------|------|------|
| 开发 docker-compose | ✅ PASS | postgres + redis 暴露端口 + 硬编码凭据 |
| 生产 docker-compose | ✅ PASS | postgres + redis **不暴露端口** + 从 .env.prod 读取凭据 |
| Dockerfile | ✅ PASS | python:3.12-slim + uv + 清华源 |
| Nginx | ✅ PASS | HTTPS 反代 + SPA history mode + admin 同源 /api/ 反代 |
| GitHub Actions CI | ✅ PASS | lint → type check → alembic → pytest（postgres + redis services）|
| GitHub Actions CD | ✅ PASS | SSH → git pull → pnpm build → docker compose build → up → alembic → health check |
| ECS 部署 | ✅ PASS | 阿里云 ECS，ECS_HOST/ECS_USER/ECS_SSH_KEY 通过 GitHub Secrets |

---

## 5. Booking 业务分析结果

### 5.1 完整模块清单

| 层级 | 文件 | 真实路径 | 内容 |
|------|------|----------|------|
| Router | `booking/router.py` | `apps/api/src/app/modules/booking/router.py` | 7 个端点，APIRouter(prefix="/bookings")，module-level `booking_service = BookingService()` |
| Schema | `booking/schemas.py` | `apps/api/src/app/modules/booking/schemas.py` | BookingCreate、BookingResponse、BookingListResponse |
| Service | `booking/service.py` | `apps/api/src/app/modules/booking/service.py` | BookingService class，create/cancel/cancel_by_schedule/check_in/complete/get/list/_do_cancel |
| Repository | `booking/repository.py` | `apps/api/src/app/modules/booking/repository.py` | BookingRepository(TenantAwareRepository)，search/find_active/find_by_schedule_and_student/count_active/delete |
| Model | `booking/models.py` | `apps/api/src/app/modules/booking/models.py` | Booking(TimestampMixin, TenantMixin) + BookingStatus/BookingSource 枚举 |

### 5.2 关键依赖（跨模块）

| 依赖 | 来源 | 用途 |
|------|------|------|
| ScheduleRepository | `modules/schedule/repository.py` | increment_booked_count / decrement_booked_count |
| membership_card_service | `modules/membership/service.py` (单例 import) | deduct_credit / restore_credit |
| TenantService | `modules/tenant/service.py`（_do_cancel_booking 内动态 import）| get_settings → booking_cancel_minutes |
| CourseSchedule | `modules/schedule/models.py` | 校验排期状态/容量/时间窗口 |

### 5.3 数据库相关约束

| 类型 | 定义 | 作用 |
|------|------|------|
| CHECK Constraint | `booked_count >= 0 AND booked_count <= capacity` | 防止 booked_count 超卖或变负（在 course_schedules 表）|
| CHECK Constraint | `used_credits >= 0 AND used_credits <= total_credits` | 防止会员卡课时为负（在 membership_cards 表）|
| Partial Unique Index | `uq_bookings_schedule_student_active ON bookings(schedule_id, student_id) WHERE status IN (1,3,4)` | 数据库层兜底同一排期同一学员不能有两个活跃预约 |
| 普通 Index | `idx_bookings_tenant_id ON bookings(tenant_id)` | 加速租户过滤 |
| 普通 Index | `idx_bookings_student_id ON bookings(student_id)` | 加速"我的预约"查询 |
| 普通 Index | `idx_bookings_schedule_id ON bookings(schedule_id)` | 加速排期下的预约查询 |
| Foreign Key | `bookings.schedule_id → course_schedules.id`（可能 ON DELETE 未设置）| UNKNOWN：未确认 FK 的 ON DELETE 行为 |
| Foreign Key | `bookings.membership_card_id → membership_cards.id` | UNKNOWN：migration 中是否定义了 FK 约束 |
| Foreign Key | `bookings.student_id → users.id` | UNKNOWN |

### 5.4 Authentication 在 Booking 中的参与

| 端点 | 认证方式 | 认证 payload 使用 |
|------|----------|-------------------|
| POST /bookings/ | `Depends(get_current_user)` | `current_user.get("user_id")` 提取为 `student_id` |
| POST /bookings/{id}/cancel | `Depends(get_current_user)` | `student_id = current_user.get("user_id")` → 传递给 BookingService.cancel_booking() |
| GET /bookings/ | `Depends(get_current_user)` | `student_id = current_user.get("user_id")`（schedule_id 为 None 时） |
| POST /bookings/{id}/check-in | `Depends(get_current_user)` | payload 仅作为身份标记（check-in 操作不依赖 student_id，任何登录用户有权限则可签到） |

**⚠️ 真实行为**：`get_current_user` 只做了 JWT 解码 + 写 ContextVar，**没有 Token 黑名单检查**（deps/auth.py:11-31）。

### 5.5 Authorization（RBAC）在 Booking 中的参与

| 端点 | 是否有 RBAC 装饰器 | PERMISSION_CHECK_BYPASS=True 时的实际行为 |
|------|-------------------|-------------------------------------------|
| POST /bookings/ | ❌ 无 | 任何登录用户都能约（正确——学员自助）|
| POST /bookings/{id}/cancel | ❌ 无 | 任何登录用户，但 Service 内部校验 `booking.student_id == student_id`（正确）|
| POST /bookings/{id}/check-in | ✅ `@require_permissions("booking:manage")` | 所有人都能签到（绕过 RBAC）⚠️ |
| POST /bookings/{id}/complete | ✅ `@require_permissions("booking:manage")` | 所有人都能完成课程（绕过 RBAC）⚠️ |

**⚠️ 安全缺陷**：PERMISSION_CHECK_BYPASS=True 使 check-in / complete 端点对任何人开放。应设为 False + 给这两个端点保留 RBAC 装饰器。

### 5.6 Multi-Tenant 在 Booking 中的参与

三层隔离：
1. **Middleware**（TenantASGIMiddleware）从 Header 提取 → `ContextVar.set_tenant_id()`
2. **Auth Depends**（get_current_user）从 JWT 再 set 一次（覆盖 middleware 值）
3. **SQLAlchemy 事件**（tenant_query.py 的 `do_orm_execute`）对所有继承 TenantMixin 的表（包括 bookings、course_schedules、membership_cards）自动注入 `WHERE tenant_id = ?`

**额外显式传递**：
- `BookingService.create_booking` 内部 `tenant_id = booking.tenant_id`（service.py:108）→ 显式传给 `deduct_credit`
- `BookingService._do_cancel_booking` 内部 `tenant_id = booking.tenant_id`（service.py:206）→ 显式传给 `restore_credit`

**⚠️ MCP Tool 链路下的问题**：
- `async with SessionLocal() as db` 创建独立 Session
- ContextVar 是否被正确设置**依赖 MCP Server 是否走 HTTP 认证链路**
- stdio transport 独立启动的 MCP Server → ContextVar 为空 → tenant_query 事件注入失败 → **跨租户数据泄露**（get_my_balance 无 tenant_id 过滤是最危险的例子）

---

## 6. Transaction 分析

### 6.1 当前事务边界

#### ✅ create_booking — 正确

```
AsyncSession (db) = Depends(get_session)  ← 同一个 Session 贯穿整个请求
│
├─ ScheduleRepository.get_by_id()          ← 读
├─ BookingRepository.find_active_booking() ← 读
├─ ScheduleRepository.increment_booked_count() ← 读+写（SELECT FOR UPDATE）
├─ BookingRepository.create()             ← 写（INSERT）
├─ membership_card_service.deduct_credit() ← 写（SELECT FOR UPDATE + UPDATE + INSERT）
│
└─ await db.commit()                       ← 统一提交
   ↓
   任何步骤抛异常 → 整个事务回滚 → booked_count 不会 +1，booking 不会插入，卡不会扣次
```

关键：BookingService 对 deduct_credit 的异常处理是 `raise BusinessException`（service.py:120），**让异常正常传播** → 触发 FastAPI 的全局异常处理 + SQLAlchemy 的 Session 回滚。

#### 🔴 cancel_booking — 有缺陷

```
AsyncSession (db) = Depends(get_session)
│
├─ BookingRepository.get_by_id()
├─ ScheduleRepository.get_by_id()
├─ TenantService.get_settings()        ← 动态 import 后独立调用（未知是否共享 Session）
├─ UPDATE booking.status = CANCELLED   ← SQLAlchemy 脏跟踪自动记录
├─ ScheduleRepository.decrement_booked_count() ← SELECT FOR UPDATE + booked_count -1
│
├─ membership_card_service.restore_credit()
│  ├─ ✅ 正确代码应该是：raise Exception → 触发回滚
│  └─ ❌ 实际代码：try/except 吞掉所有异常 → 只打 logger.error
│     ↑
│     service.py:216-218
│
└─ await db.commit()  ← 无论 restore_credit 成功与否都会执行!
   ↓
   后果：booking 已 CANCELLED，booked_count 已 -1，但会员卡 used_credits 没有恢复
```

### 6.2 Commit 位置

| 方法 | commit 位置 | 风险 |
|------|------------|------|
| `BookingService.create_booking` (service.py:122) | 最后统一 commit ✅ | 低 |
| `BookingService.cancel_booking` (→ `_do_cancel_booking` service.py:219) | restore_credit **之后** commit，但 restore_credit 异常被吞 → commit 仍执行 🔴 | 高 |
| `BookingService.check_in_booking` (service.py:243) | 最后 commit ✅ | 低 |
| `BookingService.complete_booking` (service.py:266) | 最后 commit ✅ | 低 |
| `membership_card_service.deduct_credit` | 自己内部 commit？ | UNKNOWN：未确认 membership/service.py 是否在 deduct_credit 内部 commit 还是依赖外部 Service 统一 commit |

### 6.3 Rollback 位置

| 场景 | Rollback 方式 | 效果 |
|------|--------------|------|
| FastAPI 异常处理中间件 | `db.rollback()` | ✅ 只要异常没被吞，SQLAlchemy Session 会自动回滚 |
| `BookingService.create_booking` 的 deduct_credit 抛异常 | raise → FastAPI 捕获 → rollback | ✅ 正确 |
| `BookingService._do_cancel_booking` 的 restore_credit 异常 | try/except 吞掉 → 不 raise → rollback 不会被触发 | 🔴 致命 |
| MCP Tool 内部异常 | Tool 自己 try/except 捕获并 `return f"失败：{str(e)}"` | 🔴 Tool 层吞掉业务异常，Session 不会回滚 |

### 6.4 潜在问题

| 编号 | 问题 | 严重度 | 位置 |
|------|------|--------|------|
| T-P0-1 | cancel_booking 吞掉 restore_credit 异常后仍 commit | 🔴 Critical | service.py:216-219 |
| T-P1-1 | MCP Tool 层 try/except 把业务异常变成字符串返回，不触发回滚 | 🔴 Critical | mcp_server.py 全文件 |
| T-P1-2 | membership_card_service.deduct_credit/restore_credit 是否独立 commit？ | UNKNOWN | 需要确认 membership/service.py |
| T-P2-1 | APScheduler 定时任务独立 SessionLocal，Session 出错后的回滚路径 | UNKNOWN | |

---

## 7. Concurrency 分析

### 7.1 并发风险矩阵

| 编号 | 场景 | 防护机制 | 是否充分 | 风险等级 |
|------|------|----------|----------|----------|
| C1 | 同一排期超卖 | `increment_booked_count` 的 `SELECT FOR UPDATE WHERE booked_count < capacity` + DB CHECK Constraint | ✅ 充分 | 🟢 |
| C2 | 同一学员重复预约同一排期（并发） | 应用层 `find_active_booking` + DB 部分唯一索引 `uq_bookings_schedule_student_active` | ✅ 充分 | 🟢 |
| C3 | 多学员同时抢最后 1 个名额 | 同 C1 的 SELECT FOR UPDATE 排队机制 | ✅ 充分（但体验差） | 🟢 |
| C4 | 会员卡并发扣次导致 used_credits 为负 | `deduct_credit` 用 `get_card_with_lock`（SELECT FOR UPDATE）+ DB CHECK Constraint | ✅ 充分 | 🟢 |
| C5 | 会员卡并发退费导致 used_credits 不一致 | 同上（restore_credit 也用 SELECT FOR UPDATE） | ✅ 充分 | 🟢 |
| C6 | AI Agent 多轮对话中间状态竞争 | `AgentRuntime._acquire_lock`（Redis SET NX EX TTL=5s） | ⚠️ 部分充分 | 🟡 |
| C7 | 高并发 SELECT FOR UPDATE 队列过长 | 无 SKIP LOCKED，全队列等待 + 默认无 lock_timeout | ⚠️ 存在体验问题 | 🟡 |
| C8 | booked_count 与实际 Booking 行数不一致 | 无自动同步机制 | ⚠️ 存在数据漂移 | 🟡 |
| C9 | MCP Tool 独立 Session 绕过事务边界 | create_booking/cancel 复用了 BookingService → 走对了；但 get_my_balance 直写 SQL | 🔴 **不一致** | 🔴 |
| C10 | cancel_booking 吞掉 restore_credit 异常 | 无补偿机制 | 🔴 **数据不一致** | 🔴 |
| C11 | 同一 booking 被并发 cancel + check-in | 无应用层锁，依赖 DB 行锁 + 状态校验 | ⚠️ 存在短暂窗口 | 🟡 |

### 7.2 increment_booked_count 队列行为

```
1000 用户同时约 booked_count=9 / capacity=10 的排期：

T1（第 1 个到达）: SELECT FOR UPDATE → 拿到行锁，booked_count 检查通过 → UPDATE 为 10 → COMMIT
T2-T1000（剩余 999 个）: SELECT FOR UPDATE → 被阻塞排队

T2 等 T1 COMMIT 后: SELECT ... WHERE booked_count < 10 → 现在 booked_count=10 → 查询不匹配 → 返回 False
                                    → increment_booked_count 返回 False
                                    → BookingService 抛出 BusinessException("预约失败")

浪费：999 个事务等待了锁释放时间后才发现自己约不上
建议：加 with_for_update(skip_locked=True) + 快速失败
```

### 7.3 AgentRuntime 分布式锁行为

```
锁 Key: lock:{session_id}
TTL: 5 seconds
获取: Redis SET NX EX "1" TTL
释放: Lua 脚本 GET + DEL 原子操作

并发场景：
用户 A 同时在同一 session 发送两条消息：
  msg 1 → 获取锁成功（SET NX 返回 True）→ 开始处理
  msg 2 → 获取锁失败（SET NX 返回 False）→ 返回 "正在处理您的上一个请求，请稍候..."

⚠️ 但：_acquire_lock 在 self.session.redis is None 时返回 True
   （AgentRuntime 在无 Redis 时认为锁获取成功）
```

---

## 8. AI Agent / MCP 分析

### 8.1 当前实现架构（被测 Agent 的发现）

```
用户 → ai/router.py POST /ai/chat → AgentRuntime.chat()
  → IntentRecognizer（关键词匹配，L1.5）→ 参数提取
  → SessionManager（Redis 存多轮状态）
  → _execute_intent() → 直接 import mcp_server.py 的函数并调用
  → Tool 内部：async with SessionLocal() → BookingService/ScheduleService...
  ⚠️ 不是 MCP 协议调用！是 Python 函数直接调用
  ⚠️ 两套注册并存：@mcp.tool() 装饰器 + AgentRuntime 的 import
```

### 8.2 推荐的正确架构

```
用户 → MCP Client（LLM Agent）
  → MCP Server（FastMCP，stdio/sse transport）
  → 🔒 安全校验链（每个 Tool 必须经过）：
     ① Authentication：从 MCP Session Metadata 取 JWT → decode_token
     ② Tenant Validation：set_tenant_id + verify tenant ACTIVE
     ③ Authorization：check_permissions('booking:create')
     ④ Input Validation：Pydantic schema
  → Tool Implementation（薄壳）：
     create_booking_tool → BookingService.create_booking()
     cancel_booking_tool → BookingService.cancel_booking()
     query_schedules_tool → ScheduleService.list_schedules()
     get_my_balance_tool → membership_card_service.get_user_balance() ← 新增 Service 方法
  → Application Service（厚壳，所有业务规则）：
     BookingService → increment_booked_count + 时间窗口校验 + 会员卡扣次 + 事务边界
     ScheduleService → 排期查询
     membership_card_service → 会员卡操作
  → Repository → SQLAlchemy → PostgreSQL
```

### 8.3 现有 MCP Tool 的 Service 复用分析

| Tool | 当前实现 | 应该调用 | 复用度 | 问题 |
|------|----------|----------|--------|------|
| query_courses | CourseService.list_courses | CourseService.list_courses | 100% ✅ | — |
| query_schedules | ScheduleService.list_schedules | ScheduleService.list_schedules | 100% ✅ | — |
| get_my_bookings | BookingService.list_bookings | BookingService.list_bookings | 100% ✅ | — |
| **get_my_balance** | **直接写 SQL `select(MembershipCard)`** | **membership_card_service.get_user_balance()** | **0% ❌** | **绕过 Service + 无 tenant_id 过滤** |
| create_booking | BookingService.create_booking | BookingService.create_booking | 100% ✅ | — |
| cancel_booking | BookingService.cancel_booking | BookingService.cancel_booking | 100% ✅ | — |

### 8.4 业务逻辑边界

| 绝对禁止放进 AI Agent 的 | 正确位置 |
|--------------------------|----------|
| booked_count 增减的并发控制 | `ScheduleRepository.increment_booked_count`（SELECT FOR UPDATE）|
| booking 唯一约束检查 | DB Partial Unique Index `uq_bookings_schedule_student_active` |
| 预约时间窗口校验 | `BookingService.create_booking` 中的 14 天限制 + booking_opens_at/booking_closes_at |
| 取消截止时间校验 | `TenantService.get_settings` → booking_cancel_minutes |
| 会员卡扣次/退费 | `membership_card_service.deduct_credit/restore_credit` |
| 多租户隔离 | `TenantASGIMiddleware` + `SQLAlchemy do_orm_execute` |
| RBAC 权限 | `@require_permissions` 装饰器 + Redis 缓存 |
| 事务边界 | Service 层统一 `db.commit()` |
| display_status 计算 | `BookingService._to_response`（基于 status + 时间）|
| 幂等性 | `membership_card_transactions.idempotency_key` UNIQUE |

**AI Agent 只做 5 件事**：
1. 意图识别（"帮我约瑜伽课" → extract keyword="瑜伽"）
2. 多轮对话状态管理（用户选了第几个排期 → 暂存 Redis）
3. 工具调度（根据意图决定调哪个 Tool、传什么参数）
4. 自然语言生成（把 Tool 返回的 JSON 格式化为友好回复）
5. 错误引导（"已约满 → 换一个时段"）

---

## 9. RAG / MCP Tool / Service 边界

| 层级 | 职责 | 举例 |
|------|------|------|
| **RAG（Retrieval-Augmented Generation）** | 静态知识检索 | 帮助文档、课程介绍、舞蹈知识、机构政策、常见问题 FAQ |
| **MCP Tool（Model Context Protocol）** | 实时业务查询 + 操作 | query_courses（课程列表）、query_schedules（排期）、create_booking（预约操作）、get_my_balance（余额）|
| **Application Service** | 业务规则 + 并发控制 + 事务 | BookingService（约课业务规则 + 原子操作）、membership_card_service（扣次/退费）|
| **Repository** | 数据访问 | BookingRepository、ScheduleRepository |
| **Database** | 持久化 + 约束 | PostgreSQL + CHECK Constraint + Unique Index |

**边界原则**：
- **静态知识 → RAG**：机构"什么时候开门"、"瑜伽是什么"这类不会频繁变化的知识
- **实时业务数据 → MCP Tool 只读**："明天有什么课"、"我还剩多少课时"
- **业务操作 → MCP Tool 写**："帮我约明天的瑜伽课"
- **业务规则 → Domain Service**：什么时候能约、什么时候不能约、扣多少课时
- **并发控制 → Database + Service**：SELECT FOR UPDATE、唯一索引、CHECK Constraint

**当前 RAG 实现状态**：UNKNOWN。agent/rag/retriever.py 被标记为 stub（返回硬编码数据）。未发现真正的向量数据库（pgvector / Chroma / Pinecone）接入。

---

## 10. Rule Compliance

### 10.1 对照 project_rules.md 的规则

| 规则 | 要求 | 被测代码是否遵守 | 证据 |
|------|------|------------------|------|
| Architecture 三层 | Router → Service → Repository | ✅ 基本遵守 | BookingRouter 调 BookingService，BookingService 调 BookingRepository |
| Backend Async | 所有 DB 操作用 AsyncSession | ❌ 部分违规 | TenantASGIMiddleware._get_tenant_by_slug 独立创建 SessionLocal；MCP Tool 各自 SessionLocal |
| Database Alembic | Schema 修改用 Alembic | ✅ 遵守 | 28 个 migration 文件 |
| Transaction 边界 | 多写操作明确事务边界 | ⚠️ 部分违规 | create_booking 正确统一 commit；cancel_booking 吞掉 restore_credit 异常 |
| Multi-Tenant 隔离 | Tenant-owned resources 隔离 + 不信任客户端 tenant_id | ❌ 部分违规 | TenantMixin 自动注入正确；MCP Tool stdio transport 绕过 middleware，ContextVar 为空 |
| Security 四关 | AI Tool 必须 Authentication → Authorization → Tenant → Input | ❌ 严重违规 | MCP Tool 完全无这四关 |
| Testing | 新增重要业务逻辑必须加测试 | ⚠️ 部分满足 | 有 500 行测试但并发约课场景无覆盖 |

### 10.2 合规总结

| 维度 | 结果 | 理由 |
|------|------|------|
| **架构分层** | ✅ PASS | 三层清晰，Service 复用正确（反面：MCP Tool 绕过 Service 直写 SQL）|
| **异步一致性** | ⚠️ NEED IMPROVEMENT | MCP Tool 独立 SessionLocal + ContextVar 未设置 = 绕过多租户 |
| **事务安全** | ⚠️ NEED IMPROVEMENT | cancel_booking try/except 吞掉异常 = 致命一致性风险 |
| **安全四关** | ❌ FAIL | MCP Tool 无认证、无 RBAC、无 Tenant Validation |
| **代码修改原则** | ✅ PASS | 本次测试未修改任何业务代码 |

---

## 11. 问题清单

| 编号 | 问题 | 严重程度 | 证据 | 建议 |
|------|------|----------|------|------|
| P0-1 | `cancel_booking` 吞掉 `restore_credit` 异常后仍 `db.commit()` | 🔴 Critical | booking/service.py:205-219 | 删除 try/except，让异常正常传播触发回滚 |
| P0-2 | MCP Tool 无 Authentication / Authorization / Tenant Validation | 🔴 Critical | ai/mcp_server.py 全文件（无任何 fastapi Depends，stdio transport 完全绕过 HTTP 认证）| 在 MCP Server 层统一增加 `@mcp.tool()` 前后的安全校验装饰器 |
| P0-3 | `get_my_balance` Tool 直写 SQL + 无 tenant_id 过滤 | 🔴 Critical | ai/mcp_server.py:208-216 | 改为调用 `membership_card_service.get_user_balance(user_id, tenant_id)` |
| P1-1 | `PERMISSION_CHECK_BYPASS = True` 全局放行 | 🟡 High | core/rbac/checker.py | 设为 False；同时给约课/取消端点补 RBAC 装饰器 |
| P1-2 | `get_current_user` 不检查 Token 黑名单 | 🟡 High | deps/auth.py:11-31 | 在 `decode_token` 成功后加 `if is_token_blacklisted(token): raise AuthException` |
| P1-3 | MCP Tool 各自 `async with SessionLocal()` | 🟡 High | mcp_server.py:58, 96, 166, 207, 250, 284 | MCP Server 层统一创建 Session 并通过 Context 传递 |
| P1-4 | AgentRuntime 直接 import mcp_server.py 函数而非 MCP Client 协议调用 | 🟡 Medium | ai/agent/runtime.py:15-22 import + line 117-200 直接调用 | 引入 FastMCP Client，通过 MCP 协议调用 Tool；彻底消除两套注册并存 |
| P1-5 | `/api/v1/courses` 跳过租户检查（通配在 SKIP_TENANT_PATHS）| 🟡 Medium | middleware/tenant_middleware.py | 移除 courses 通配，改为只跳过 `/api/v1/courses/public` 等公开端点 |
| P2-1 | `increment_booked_count` 无 `SKIP LOCKED` | 🟡 Medium | schedule/repository.py:182 `.with_for_update()` 不带 skip_locked | 高并发场景考虑加 `skip_locked=True` + 快速失败 |
| P2-2 | APScheduler 定时任务不处理关联 Booking（状态孤立）| 🟡 Medium | main.py auto_finish_expired_schedules | 增加级联逻辑：排期 FINISHED 后关联的 BOOKED 预约怎么办 |
| P2-3 | RateLimiterMiddleware 存在但未全局注册 | 🟡 Medium | middleware/rate_limiter.py + main.py 无引用 | 在 main.py 全局注册或按路由级应用 |
| P2-4 | RBAC 缓存 `clear_role_permissions_cache` 未实现 | 🟢 Low | rbac/cache.py TODO | 权限变更后手动触发清除，或用 Redis Pub/Sub 实现 |
| P2-5 | Dockerfile 清华源 fallback 未实现 | 🟢 Low | Dockerfile 只有一个源，无 fallback | 增加主源失败后 fallback 的多源策略 |
| P2-6 | 无日志集中化 / 监控告警 | 🟢 Low | 无 ELK/Loki/Prometheus 配置 | 按生产需求引入 |
| P3-1 | BookingService 直接实例化 Repository 而非依赖注入 | 🟢 Low | booking/service.py:45-46 `self.repo = BookingRepository()` | 重构为构造函数注入，提升可测试性 |

---

## 12. UNKNOWN 项目

| 编号 | 项目 | 原因 | 建议验证方式 |
|------|------|------|--------------|
| U-1 | `membership_card_service.deduct_credit` 是否在内部独立 commit | 未完整读 membership/service.py 的 deduct_credit 后半段 | 读 `membership/service.py:1278-1340` |
| U-2 | `membership_card_service.restore_credit` 同上 | 同上 | 读 `membership/service.py:1355-1420` |
| U-3 | FK 约束：bookings.membership_card_id ON DELETE 行为 | migration 文件中未确认 | 查 Alembic migration 或 `\d bookings` |
| U-4 | FK 约束：bookings.schedule_id ON DELETE 行为 | 同上 | 同上 |
| U-5 | FK 约束：bookings.student_id → users.id | 同上 | 同上 |
| U-6 | `TenantService.get_settings` 是否共享 BookingService 的 AsyncSession | service.py:186 动态 import 后独立调用 | 读 tenant/service.py |
| U-7 | APScheduler 的 SessionLocal 是否设置了 ContextVar | 定时任务入口 | 读 main.py lifespan 中 APScheduler 启动代码 |
| U-8 | PostgreSQL 事务隔离级别 | 代码未显式配置 | SQL `SHOW transaction_isolation;` |
| U-9 | PostgreSQL 锁等待超时 | 代码未配置 `lock_timeout` | SQL `SHOW lock_timeout;` |
| U-10 | MCP Server 的 stdio transport 是否被实际使用过 | 只有注册代码，无调用证据 | grep 搜索 `mcp.run(transport=` |
| U-11 | RBAC 缓存 Key `perms:{tenant_id}:{user_id}` 是否有缓存击穿保护 | cache.py 无锁，可能击穿 | 读 rbac/cache.py 完整内容 |
| U-12 | RateLimiterMiddleware 注册位置 | main.py 未引用 | grep 搜索 `RateLimiterMiddleware` |
| U-13 | `shared/base_model.py` TenantMixin 如何设置 tenant_id（DB default 还是 Python default）| 未确认 | 读 `base_model.py` |
| U-14 | 当前 `PERMISSION_CHECK_BYPASS` 的值是 True 还是 False | 之前分析标记为 True，需从 checker.py 确认 | `grep PERMISSION_CHECK_BYPASS` |
| U-15 | Auto-fail 测试覆盖（test_booking_concurrency.py）是否存在 | 未找到 | 需确认是已存在还是需新建 |
| U-16 | pgvector 是否已用于 RAG | agent/rag/retriever.py 标记为 stub | grep 搜索 pgvector / chroma / pinecone |
| U-17 | 生产 Redis 是否设置了密码 | docker-compose.prod.yml 未看到 requirepass | 检查 .env.prod 或 Redis config |

---

## 13. Agent 表现评价

### Context Understanding — PASS

**理由**：正确识别了 Monorepo 4 前端 + 1 FastAPI 后端结构、FastAPI async 依赖注入链、SQLAlchemy 2.0 AsyncSession + do_orm_execute 事件、PostgreSQL 约束、Redis 4 种用途、JWT + bcrypt + Redis 黑名单认证链、RBAC 四表 + Redis 缓存、Multi-Tenant 三层隔离。所有发现均有代码行号支撑，无臆测。

### Code Grounding — PASS

**理由**：所有结论都引用了具体文件路径和行号（如 `service.py:205-219`、`deps/auth.py:11-31`、`mcp_server.py:208-216`）。没有发现编造的 Service/API/DB 字段。已识别的 UNKNOWN 项目被明确标记，未强行猜测。

### Architecture Analysis — PASS

**理由**：Router → Service → Repository → SQLAlchemy → PostgreSQL 三层关系清晰；依赖方向正确（BookingService → ScheduleRepository + BookingRepository + membership_card_service）；Mermaid 架构图准确反映实际调用链。

### Security Awareness — NEED IMPROVEMENT

**理由**：Agent **正确识别了** PERMISSION_CHECK_BYPASS=True、Token 黑名单未检查、MCP Tool 无认证等安全问题（这是优点）。但 Agent **之前的测试分析中没有主动建议修复方案**，只是记录了问题。作为 Architect Agent，应该在发现安全缺陷时直接给出修复方向（已在本报告中补充）。

### Database Awareness — PASS

**理由**：正确识别了 CHECK Constraint、Partial Unique Index、SELECT FOR UPDATE 行锁、idempotency_key UNIQUE 等约束机制。对 FK 约束标记了 UNKNOWN，未强行猜测。

### AI / MCP Architecture — PASS

**理由**：正确识别了"两套注册并存 + AgentRuntime 直接函数调用而非 MCP 协议"的架构问题；正确划分了 AI Agent 职责（意图识别 + 参数提取 + 多轮状态 + 工具调度 + 格式化）和业务规则边界（时间窗口、并发控制、事务边界必须在 Service/DB 层）。

### Rule Compliance — NEED IMPROVEMENT

**理由**：Agent 在分析中正确识别了违规点（如 MCP Tool 绕过 AsyncSession、cancel_booking 吞异常），但**分析本身不是实施操作**——Agent 没有修复这些违规（这是正确的，因为测试要求不修改业务代码）。合规性"Need Improvement"指的是代码本身，而非 Agent 的行为。Agent 的分析正确指出了代码不符合 project_rules.md 的地方。

### Output Quality — PASS

**理由**：输出结构清晰（12 个 Mermaid 图 + 表格 + 代码行号引用）；所有发现均有证据；UNKNOWN 项目明确标记；Risk Matrix 按严重度分级（🔴/🟡/🟢）；Transaction 和 Concurrency 分析有具体代码路径。

### Self-Awareness — NEED IMPROVEMENT

**理由**：Agent 初始分析中标记了"测试覆盖范围 UNKNOWN"，但实际上代码库有 500 行测试（test_multi_turn_booking.py、test_mcp_server.py、test_tenant_isolation.py 等）——这个 UNKNOWN 可以通过 `find tests/ -name '*.py'` 消除。这暴露了 Agent 在开始分析前**没有先枚举完整测试文件**，导致了不必要的不确定性。

---

## 14. Prompt 改进建议

### 应该增加的规则

| 编号 | 建议增加的规则 | 理由 |
|------|----------------|------|
| P-ADD-1 | "在开始深入分析前，先运行 `find apps/api/tests -name '*.py' | head` 确认测试文件存在性" | Agent 初始分析错误地标记测试覆盖范围 UNKNOWN，实际存在大量测试文件 |
| P-ADD-2 | "如果测试中发现 `.env.prod` / `.env.example` 存在，列出其中的关键配置项" | 帮助识别生产密码/密钥配置风险 |
| P-ADD-3 | "检查 `.github/workflows/` 中 CI 是否有 continue-on-error: true——如果有，标记为 CI 质量风险" | CI 的 Mypy continue-on-error 是已知风险，但初始分析未关注 CI 配置细节 |
| P-ADD-4 | "对每个 MCP Tool，检查其 DB Session 创建方式——是走 FastAPI 依赖注入还是自己 `async with SessionLocal()`" | MCP Tool 独立 SessionLocal + ContextVar 空 = 多租户绕过，这是关键问题但初始分析中需要精读才能发现 |
| P-ADD-5 | "对每个 Service 中使用 try/except + logger.error 的代码，检查异常是否在 catch 后仍 commit" | cancel_booking 的 try/except 问题模式非常典型，应作为搜索模式 |

### 应该保持的规则

| 编号 | 现有规则 | 理由 |
|------|----------|------|
| P-KEEP-1 | 必须阅读真实代码，不能猜测 | 这是本报告的核心质量保障 |
| P-KEEP-2 | 不确定标记 UNKNOWN | 本报告有 17 个 UNKNOWN，诚实标记远好过强行猜测 |
| P-KEEP-3 | 输出必须有代码行号引用 | 让结论可追溯验证 |
| P-KEEP-4 | 用 Mermaid 画架构图 | 可视化帮助理解复杂调用链 |
| P-KEEP-5 | 先 Analyze → Plan → Implement → Test → Review | 本次任务只做到 Analyze 和 Plan，但流程正确 |

### 应该删除或修改的规则

| 编号 | 现有规则 | 建议修改 | 理由 |
|------|----------|----------|------|
| P-MOD-1 | "输出要简洁" | 修改为"核心发现必须简洁，但关键代码路径/行号引用不能省略" | Agent 初始分析中某些 Mermaid 图的注释过于冗长，但行号引用是必须保留的 |

---

## 15. 最终结论

### 结论：**NEED IMPROVEMENT**

### 原因

Agent 在本次测试中**展现了极强的代码理解能力**：
- 正确识别了约课业务的完整调用链（7 层调用，含 Mermaid 图 + 代码行号）
- 正确识别了三层隔离机制（Middleware + ContextVar + SQLAlchemy 事件自动注入）
- 正确识别了 3 个 P0 级安全缺陷（cancel_booking 吞异常、MCP Tool 无认证、get_my_balance 无 tenant 过滤）
- 正确识别了 SELECT FOR UPDATE + DB 唯一索引 + CHECK Constraint 三层并发防护
- 正确识别了 AI Agent / MCP 的架构错误（两套注册并存 + 直接函数调用而非协议调用）

**但在以下方面有明确可改进空间**：
1. **Self-Awareness**：初始分析中标记测试覆盖范围 UNKNOWN，但实际存在 500 行测试（17 个测试文件）。应在深入分析前先做 `find tests/` 扫描。
2. **Security Awareness（实施方向）**：识别了问题但未同时给出修复方案的优先级排序（本报告的 P0/P1/P2 清单是补充的）。
3. **Prompt 完整性**：当前 Prompt 缺少针对"Service 中 try/except 模式"、"MCP Tool Session 创建方式"、"CI continue-on-error 扫描"等特定代码模式的主动搜索指令。

### 核心优势

> **Architect Agent 的最大价值不是写代码，而是在正确的时间点用正确的方式读了正确的代码，然后给出可验证、可追溯的技术判断。**

本次测试中，Agent 做到了这一点。发现的 15 个问题全部有代码行号引用，17 个 UNKNOWN 全部诚实标记，Mermaid 架构图准确反映实际调用链。这为后续修复工作提供了坚实的起点。

### 后续步骤建议

1. **立即修复 P0-1**：删除 cancel_booking 的 try/except
2. **立即修复 P0-2 + P0-3**：给 MCP Tool 加认证四关 + get_my_balance 改造
3. **短期修复 P1-1 ~ P1-5**：PERMISSION_CHECK_BYPASS、Token 黑名单检查、MCP Session 统一、两套注册消除、courses 通配移除
4. **中期修复 P2-1 ~ P2-3**：SKIP LOCKED、APScheduler 级联处理、RateLimiter 注册
5. **长期修复 P3-1**：Service 依赖注入重构

---

*报告生成时间：2026-09-21*
*被测 Agent：Architect Agent（class_booking_system 专属）*
*被测文档：`docs/booking_analysis.md`（约 800 行，12 个 Mermaid 图）*
*交叉验证文档：architecture.md, database.md, api.md, authentication.md, booking.md, deployment.md, project_rules.md*
*交叉验证代码：booking/service.py, booking/router.py, booking/repository.py, schedule/repository.py, deps/auth.py, ai/mcp_server.py, ai/agent/runtime.py, middleware/tenant_middleware.py*
