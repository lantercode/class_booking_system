# Backend Agent 测试报告 —— 学生约课后端实现

## 1. 基本信息

| 项目 | 值 |
|------|-----|
| 测试对象 | 学生约课（Student Booking）后端实现全链路 |
| 测试日期 | 2026-09-21 |
| 测试版本 | v1.0 |
| 代码基准 | 当前 `apps/api/src/app/` 真实代码 |
| 修改业务代码 | 否（仅读取和分析） |

---

## 2. 完整调用链图

```
┌─────────────┐
│  前端 (小程序) │
└──────┬──────┘
       │ POST /api/v1/bookings
       │ Header: Authorization: Bearer <token>
       │ Header: x-tenant-id: <id>
       │ Body: { schedule_id, source, membership_card_id? }
       ▼
┌─────────────────────────────────────────────────────────┐
│  TenantASGIMiddleware                                    │
│  middleware/tenant_middleware.py:40                       │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 1. _should_skip_tenant() → False（不在 SKIP 列表） │ │
│  │ 2. _extract_tenant() → 读 x-tenant-id header     │ │
│  │ 3. set_tenant_id(tenant_id) → ContextVar          │ │
│  └───────────────────────────────────────────────────┘ │
└──────┬──────────────────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────────────────┐
│  get_session() (FastAPI Depends)                         │
│  core/database.py:16                                    │
│  ┌───────────────────────────────────────────────────┐ │
│  │ async with SessionLocal() as session:             │ │
│  │   yield session                                   │ │
│  │   except → await session.rollback()               │ │
│  └───────────────────────────────────────────────────┘ │
└──────┬──────────────────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────────────────┐
│  get_current_user() (FastAPI Depends)                    │
│  deps/auth.py:11                                        │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 1. 检查 Authorization header 格式                 │ │
│  │ 2. decode_token(token) → payload                 │ │
│  │ 3. set_tenant_id(payload["tenant_id"])            │ │
│  │ 4. set_user_id(payload["user_id"])                │ │
│  │ 5. set_role_id(payload["role_id"])                │ │
│  │ 6. return payload (dict)                          │ │
│  └───────────────────────────────────────────────────┘ │
└──────┬──────────────────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────────────────┐
│  BookingRouter.create_booking()                          │
│  modules/booking/router.py:22                           │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 无 @require_permissions 装饰器！                  │ │
│  │ student_id = current_user.get("user_id")          │ │
│  │ booking_service.create_booking(db, data, ...)     │ │
│  └───────────────────────────────────────────────────┘ │
└──────┬──────────────────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────────────────┐
│  BookingService.create_booking()                         │
│  modules/booking/service.py:48                          │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 业务校验：                                         │ │
│  │   schedule 存在？ status=NORMAL？                 │ │
│  │   booked_count < capacity？                       │ │
│  │   now <= start_at？                               │ │
│  │   start_at <= now + 14days？                      │ │
│  │   booking_opens_at / booking_closes_at 窗口？     │ │
│  │   学员是否已有有效预约？（find_active_booking）     │ │
│  │                                                    │ │
│  │ 并发控制：                                         │ │
│  │   schedule_repo.increment_booked_count(db, sid)  │ │
│  │     → SELECT ... FOR UPDATE (schedule row 锁)      │ │
│  │     → booked_count += 1（内存修改）               │ │
│  │                                                    │ │
│  │ 创建 Booking：                                     │ │
│  │   repo.create(db, booking_data)                    │ │
│  │     → TenantAwareRepository.create()              │ │
│  │       → 注入 tenant_id                             │ │
│  │       → BaseRepository.create()                   │ │
│  │         → INSERT ...                               │ │
│  │         → ⚠️ auto_commit=True 默认 → COMMIT 1       │ │
│  │                                                    │ │
│  │ 会员卡扣次（可选）：                               │ │
│  │   membership_card_service.deduct_credit(db, ...)  │ │
│  │     → SELECT card FOR UPDATE                       │ │
│  │     → 检查 status/expire_at/余额                    │ │
│  │     → used_credits += 1（内存修改）               │ │
│  │     → INSERT txn（flush，未 commit）               │ │
│  │                                                    │ │
│  │ ⚠️ 外层第二次 commit()：                           │ │
│  │   await db.commit() → COMMIT 2                     │ │
│  └───────────────────────────────────────────────────┘ │
└──────┬──────────────────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────────────────┐
│  PostgreSQL                                              │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 表 bookings:                                       │ │
│  │   ├── PK id (BigInteger)                          │ │
│  │   ├── FK schedule_id → course_schedules.id        │ │
│  │   ├── FK student_id → users.id                    │ │
│  │   ├── Partial UNIQUE: (schedule_id, student_id)    │ │
│  │   │   WHERE status IN (1, 3, 4)                    │ │
│  │   ├── Index uq_bookings_schedule_student_active    │ │
│  │   ├── Index idx_bookings_student                  │ │
│  │   └── Index idx_bookings_schedule                 │ │
│  │                                                    │ │
│  │ 表 course_schedules:                               │ │
│  │   ├── booked_count (SmallInteger)                 │ │
│  │   ├── capacity (SmallInteger)                     │ │
│  │   └── CHECK: booked_count <= capacity              │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 逐层代码定位

### 3.1 Router

| 项 | 值 |
|----|-----|
| 文件 | `apps/api/src/app/modules/booking/router.py` |
| 路由前缀 | `APIRouter(prefix="/bookings")` |
| 注册位置 | `main.py:192` → `booking_router, prefix="/api/v1"` |
| 完整路径 | `POST /api/v1/bookings` |

**`create_booking` 端点详细：**

- `router.py:22-41` — 装饰器：`@router.post("/")`
- **无** `@require_permissions()` 装饰器（对比 check_in_booking 有 `@require_permissions("booking:manage")`）
- 请求参数：
  - `data: BookingCreate = Body(...)`
  - `db: AsyncSession = Depends(get_session)`
  - `current_user: dict = Depends(get_current_user)`
- 业务逻辑：从 `current_user.get("user_id")` 提取 `student_id`，调用 `booking_service.create_booking(db, data, student_id=student_id)`

### 3.2 Schema

| 项 | 值 |
|----|-----|
| 文件 | `apps/api/src/app/modules/booking/schemas.py` |
| 类 | `BookingCreate`（line 12-18） |

**BookingCreate 字段：**

```python
schedule_id: int = Field(...)          # 必填：排期ID
source: str | None = Field("self")     # 可选：self / admin / teacher
membership_card_id: int | None         # 可选：会员卡ID
```

Pydantic v2，无业务校验器（validator），仅类型和默认值校验。

### 3.3 Service

| 项 | 值 |
|----|-----|
| 文件 | `apps/api/src/app/modules/booking/service.py` |
| 类 | `BookingService`（line 41） |
| 依赖 | `BookingRepository` + `ScheduleRepository` + `membership_card_service` |

**`create_booking` 方法（line 48-126）完整步骤：**

| 步骤 | 行号 | 操作 | SQL |
|------|------|------|-----|
| 1 | 60 | 查排期 | `SELECT course_schedules WHERE id = ?` |
| 2 | 64-65 | 校验 status=NORMAL | 内存判断 |
| 3 | 67-68 | 校验 booked_count < capacity | 内存判断 |
| 4 | 72-73 | 校验 now <= start_at | 内存判断 |
| 5 | 75-77 | 校验 start_at <= now + 14days | 内存判断 |
| 6 | 79-82 | 校验 booking_opens_at / closes_at | 内存判断 |
| 7 | 84-86 | 查已有有效预约 | `SELECT bookings WHERE schedule_id=? AND student_id=? AND status IN (1,3,4)` |
| **8** | **88-90** | **原子占位** | `SELECT course_schedules WHERE id=? AND status=1 AND booked_count<capacity FOR UPDATE` |
| 9 | 92-94 | source 校验 | 内存判断 |
| **10** | **105** | **创建 Booking（auto_commit=True）** | `INSERT bookings ...` → **COMMIT 1** |
| **11** | **107-120** | **会员卡扣次（可选）** | `SELECT cards FOR UPDATE` → `UPDATE used_credits` → `INSERT txn`（flush 未 commit） |
| **12** | **122** | **外层 commit** | **COMMIT 2** |

### 3.4 Repository

| 项 | 值 |
|----|-----|
| BookingRepository 文件 | `apps/api/src/app/modules/booking/repository.py` |
| 继承 | `TenantAwareRepository[Booking]` |
| model_class | `Booking` |
| ScheduleRepository 文件 | `apps/api/src/app/modules/schedule/repository.py` |
| 继承 | `TenantAwareRepository[CourseSchedule]` |

**BookingRepository 方法：**

| 方法 | 行号 | 用途 |
|------|------|------|
| `search()` | 22-84 | 分页搜索（手动注入 tenant_id） |
| `find_active_booking()` | 109-137 | 查有效预约（手动注入 tenant_id） |
| `find_by_schedule_and_student()` | 86-107 | 按排期+学员查预约（手动注入 tenant_id） |
| `get_by_id()` | 继承 TenantAwareRepository | 自动 tenant_id 过滤 |
| `create()` | 继承 TenantAwareRepository → BaseRepository | 自动注入 tenant_id，**auto_commit=True** |

**ScheduleRepository 关键方法：**

| 方法 | 行号 | SQL | 行锁 | 备注 |
|------|------|-----|------|------|
| `increment_booked_count()` | 169-191 | `SELECT ... WHERE id=? AND status=1 AND booked_count<capacity FOR UPDATE` | ✅ 有 | **无 `skip_locked`** |
| `decrement_booked_count()` | 193-208 | `SELECT ... WHERE id=? FOR UPDATE` | ✅ 有 | 取消预约时调用 |

### 3.5 Model

**Booking Model**（`modules/booking/models.py:26-75`）：

| 字段 | 类型 | 约束 |
|------|------|------|
| id | BigInteger | PK |
| public_id | PG_UUID | UNIQUE, DEFAULT uuid4() |
| tenant_id | BigInteger | FK → tenants.id, NOT NULL |
| schedule_id | BigInteger | FK → course_schedules.id, ON DELETE RESTRICT |
| student_id | BigInteger | FK → users.id, ON DELETE RESTRICT |
| status | SmallInteger | 1=BOOKED, 2=CANCELLED, 3=CHECKED_IN, 4=COMPLETED, 5=NO_SHOW |
| source | String(20) | self/admin/teacher, DEFAULT self |
| membership_card_id | BigInteger | NULLABLE |
| booked_at | DateTime | server_default=now() |
| cancelled_at | DateTime | NULLABLE |
| cancelled_reason | String(255) | NULLABLE |
| checked_in_at | DateTime | NULLABLE |

**Booking 表索引约束：**

```sql
-- Partial UNIQUE：同一学员在同一排期只能有一个有效预约
CREATE UNIQUE INDEX uq_bookings_schedule_student_active
ON bookings (schedule_id, student_id)
WHERE status IN (1, 3, 4);

CREATE INDEX idx_bookings_student  ON bookings (tenant_id, student_id, status);
CREATE INDEX idx_bookings_schedule ON bookings (tenant_id, schedule_id, status);
```

**CourseSchedule CHECK 约束**（`modules/schedule/models.py:67-69`）：

```sql
CHECK (booked_count <= capacity AND booked_count >= 0)
```

### 3.6 数据库约束总览

| 约束 | 类型 | 位置 | 保护什么 |
|------|------|------|----------|
| `uq_bookings_schedule_student_active` | Partial UNIQUE | models.py:66-72 + alembic | 同一学员重复约同一排期（有效状态） |
| `chk_schedule_capacity` | CHECK | schedule/models.py:67-69 | booked_count 不超过 capacity |
| `chk_schedule_time` | CHECK | schedule/models.py:66 | end_at > start_at |
| `course_schedules.id` | SELECT FOR UPDATE | schedule/repository.py:182 | 并发预约时对排期行加锁 |
| `membership_cards.id` | SELECT FOR UPDATE | membership/service.py:480-504 | 并发扣次时对卡行加锁 |

---

## 4. Authentication 参与方式

| 项 | 值 |
|----|-----|
| 文件 | `apps/api/src/app/deps/auth.py:11-31` |
| 依赖函数 | `get_current_user` |
| 触发条件 | 所有需要认证的路由（通过 `Depends(get_current_user)`） |
| Token 格式 | `Authorization: Bearer <JWT>` |
| 解码 | `decode_token(token)` — 返回 payload dict 或 None |
| ContextVar 设置 | `set_tenant_id()`, `set_user_id()`, `set_role_id()` |
| **不检查** | Token 黑名单（Redis 黑名单功能已实现但未调用） |

JWT Payload 预期包含：

```json
{
  "user_id": 123,
  "tenant_id": 1,
  "role_id": 2
}
```

在 `router.py:35` 通过 `current_user.get("user_id")` 提取学员身份。

---

## 5. Authorization / RBAC 参与方式

### 5.1 当前状态：RBAC **被绕过**

`core/rbac/checker.py:39`：

```python
PERMISSION_CHECK_BYPASS = True   # ⚠️ 临时开关，正式环境应改回 False
```

### 5.2 Booking Router 的权限装饰器使用情况

| 端点 | `@require_permissions` | 说明 |
|------|----------------------|------|
| `create_booking` | **无** | 任何认证用户可约课 |
| `list_bookings` | **无** | 任何认证用户可查列表 |
| `get_booking` | **无** | 任何认证用户可查详情 |
| `cancel_booking` | **无** | 任何认证用户可取消 |
| `cancel_booking_by_schedule` | **无** | 任何认证用户可取消 |
| `check_in_booking` | ✅ `booking:manage` | **有装饰器**，但被 BYPASS |
| `complete_booking` | ✅ `booking:manage` | **有装饰器**，但被 BYPASS |

### 5.3 即使开启 BYPASS=False，存在的问题

`router.py:29-41` 的 `create_booking` 没有任何权限装饰器。修复 BYPASS 后，所有认证用户仍然可以创建预约——这可能没问题（学员确实应该能约课），但缺少角色粒度控制（比如 teacher 能不能代约？）。

---

## 6. Multi-Tenant 参与方式

三层隔离机制：

### Layer 1: ASGI Middleware

| 项 | 值 |
|----|-----|
| 文件 | `middleware/tenant_middleware.py:40` |
| 作用 | 从 header 提取 tenant_id，注入 ContextVar |
| SKIP 路径 | `/api/v1/courses` 等（line 24-37） |
| 清理 | finally 中 `set_tenant_id(None)` |

### Layer 2: ContextVar 存储

| 项 | 值 |
|----|-----|
| 文件 | `core/tenant_context.py:3-5` |
| 变量 | `ContextVar("tenant_id")`, `ContextVar("user_id")`, `ContextVar("role_id")` |
| 设置时机 | `get_current_user()` 中设置（auth.py:27-29） |

### Layer 3: SQLAlchemy ORM 查询自动注入

| 项 | 值 |
|----|-----|
| 文件 | `core/tenant_query.py:29-96` |
| 机制 | `SessionEvents.do_orm_execute` → `with_loader_criteria()` |
| 触发 | ORM Query 执行时自动拦截 |
| 效果 | 对所有有 `tenant_id` 字段的 Model 自动添加 `WHERE tenant_id = ?` |

### Layer 3b: TenantAwareRepository 手动注入

| 项 | 值 |
|----|-----|
| 文件 | `core/base_repository.py:396-457` |
| 覆盖方法 | `create()`, `get_by_id()`, `get_all()`, `get_paginated()`, `count()` |
| BookingRepository | **部分覆盖**：`search()`, `find_active_booking()` 等方法在内部**手动**加 `get_tenant_id()` 过滤（repository.py:66-71, 116-134） |

### ⚠️ 重要发现：BookingRepository 绕过了 TenantAwareRepository

`BookingRepository.search()` 等自定义方法**没有**调用 `super().get_by_id()` 等 TenantAware 方法，而是**手动**获取 tenant_id 并在 query 中添加。这导致：
- 如果忘记加 tenant_id，可能泄露数据
- `find_by_schedule_and_student()` 有 tenant_id 检查（line 102-104）✅
- `find_active_booking()` 有 tenant_id 检查（line 132-134）✅

---

## 7. Redis 参与方式

### 7.1 直接参与约课流程？

**❌ 否。** 在 booking module 所有 .py 文件中 grep `redis|Redis` 无任何匹配。

### 7.2 间接参与？

| 场景 | 是否用 Redis | 代码位置 |
|------|-------------|----------|
| RBAC 权限缓存 | ✅ 是 | `core/rbac/cache.py` + `checker.py:154` |
| 约课时 Redis 锁 | ❌ 否 | 无 |
| Token 黑名单 | ⚠️ 已实现但未接入 | `auth.py` 的 `_redis_client` 存在但 `decode_token` 不检查黑名单 |
| 速率限制 | ⚠️ 中间件已定义但未 add_middleware | `main.py:177-181` 定义了 RATE_LIMIT_CONFIG 但未在 lifespan 中注册 |
| AI Agent 分布式锁 | ✅ 是（仅 AI 层） | `ai/agent/runtime.py` 用 `SET NX EX` 锁 |

### 7.3 总结

Redis 在当前**纯 HTTP 约课流程中不直接参与**。仅用于 RBAC 权限缓存（checker 会先查 Redis 缓存，未命中再查 DB）。

---

## 8. Transaction 边界分析

### 8.1 get_session() 提供的边界

`core/database.py:16-21`：
```python
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

- 外层 try/except 只负责 rollback 和 re-raise
- **没有自动 commit** — 依赖调用方自行 commit

### 8.2 BookingService.create_booking 的提交行为

**⚠️ 发现双重 commit 问题：**

```
时间线：
───────────────────────────────────────────────────────────
|  T1  repo.create(db, data)                              |
|      → TenantAwareRepository.create() 注入 tenant_id     |
|      → BaseRepository.create() [auto_commit=True]        |
|        → INSERT bookings                                 |
|        → 🔴 COMMIT 1  ← ⚠️ 第一次提交                    |
|                                                           |
|  T2  membership_card_service.deduct_credit(db, ...)     |
|      → SELECT card FOR UPDATE                            |
|      → UPDATE card (内存)                                |
|      → INSERT txn（flush，没有 commit）                 |
|      → 如果这里抛异常（卡过期、余额不足...）               |
|                                                           |
|  T3  await db.commit() [永远不会执行]                    |
|                                                           |
|  → 异常传播到 get_session 的 except → rollback()          |
|    但 COMMIT 1 已经发生！booking 行已持久化！             |
└───────────────────────────────────────────────────────────
```

**影响：** 如果会员卡扣次失败（会员卡已过期、余额不足等），booking 记录已在 COMMIT 1 时持久化，无法被后续 rollback 撤销。结果是：
- booking 存在（status=BOOKED）
- 但 scheduled.booked_count 已 +1（也在同一次 COMMIT 里）
- 会员卡扣款失败导致 txn 表没有对应消费记录
- 学员没有被扣课时但占用了名额

**修复建议：** 在 `BookingService.create_booking` 调用 `self.repo.create(db, booking_data, auto_commit=False)`。

### 8.3 cancel_booking 的提交行为

`_do_cancel_booking()`（line 165-226）：
- 不调用任何 `repo.create()` / `repo.update()`
- 所有修改都是内存操作：修改 booking.status、schedule.booked_count、membership_card.used_credits
- **只有 line 222 一处** `await db.commit()`

✅ 这是正确的 — 单一 commit 保证原子性。如果 `restore_credit` 失败，会抛 BusinessException 触发 rollback。

### 8.4 Transaction 边界总结

| 操作 | commit 次数 | 是否原子 | 原因 |
|------|-----------|---------|------|
| create_booking | **2 次** | ❌ **非原子** | BaseRepository.auto_commit=True 导致第一次提交在 deduct_credit 之前 |
| cancel_booking | 1 次 | ✅ 原子 | 所有修改在最后统一 commit |
| check_in_booking | 1 次 | ✅ 原子 | 同上 |
| complete_booking | 1 次 | ✅ 原子 | 同上 |

---

## 9. Concurrency 分析

### 9.1 并发场景矩阵

| 场景 | 保护机制 | 是否充分 | 风险 |
|------|---------|---------|------|
| 学员 A 和 B 同时约最后一个名额 | `increment_booked_count` SELECT FOR UPDATE + 条件 `booked_count < capacity` | ✅ 充分 | **请求排队**（无 skip_locked） |
| 同一学员重复发起约课（双击提交） | Partial UNIQUE + find_active_booking + increment_booked_count | ⚠️ 部分 | TOCTOU 窗口内可能两次都通过 find_active_booking，靠 UNIQUE 兜底 |
| 约课和取消同时操作同一排期 | 都对 schedule 行 FOR UPDATE | ✅ 充分 | 锁互斥 |
| 会员卡并发扣次 | `get_card_with_lock()` FOR UPDATE | ✅ 充分 | 悲观锁保护 |
| AI Agent 重复调用约课 | 无专门去重 | ⚠️ 有风险 | 靠 UNIQUE INDEX 和幂等键部分保护 |

### 9.2 关键并发风险详解

#### 风险 1：TOCTOU 在同一学员重复约课

```
请求 A（第一只约课）     请求 B（第二只约课 — 双击）
─────────────────       ─────────────────────────
find_active_booking()   （同时发起）
  → 返回 None ✅           → 返回 None ✅
                          
increment_booked_count() increment_booked_count()
  → 等待 schedule 锁          → 等待 schedule 锁
  → 抢到锁，booked_count++    → 锁被释放后，抢到锁
                              → 但此时 booked_count 已经 >= capacity？
                              → 条件 booked_count < capacity 不成立 → False ✅
```

实际上 `increment_booked_count` 的 WHERE 条件 `booked_count < capacity` 在 FOR UPDATE 锁下执行，保证了原子性。**这个场景是安全的**。

#### 风险 2：同一学员的 find_active_booking TOCTOU + UNIQUE 兜底

```
请求 A                   请求 B
──────                   ──────
find_active_booking()   find_active_booking()
  → None ✅                → None ✅

increment_booked_count  increment_booked_count
  → 成功，booked_count++   → 成功（条件仍满足），booked_count++
  → COMMIT 1               → COMMIT 1

INSERT bookings          INSERT bookings
  → 成功 ✅                → UNIQUE CONSTRAINT VIOLATION ❌
                          → get_session rollback ✅
```

✅ 数据库 Partial UNIQUE 兜底了这个场景。但 B 请求会收到数据库 ConstraintViolationError，错误信息不够友好（是数据库原始错误而非业务错误）。

#### 风险 3：`increment_booked_count` 缺少 SKIP LOCKED

```python
# 当前代码 schedule/repository.py:182
.with_for_update()

# 对比 schedule/repository.py:150（find_conflicts 中用了）
.with_for_update(skip_locked=True)
```

高并发最后名额抢战时，所有请求会在 `SELECT FOR UPDATE` 处**排队等待**，而不是快速失败。`skip_locked=True` 能让后来的请求立即跳过被锁行，快速返回"已满"错误。

**严重度：** 🟡 Medium（不影响正确性，但影响高并发性能和用户体验）

#### 风险 4：AI Agent 重复调用无应用层去重

当前 HTTP 约课入口靠：
1. JWT 认证（每请求带 token）
2. Partial UNIQUE INDEX（DB 层兜底）
3. 排期行 FOR UPDATE（并发控制）

但 AI Agent 如果**绕过 HTTP**（直接调 Service 层），可以用不同 user_id 绕过 `find_active_booking`。MCP Tool 当前实现是调 HTTP，所以暂时安全。但如果未来 MCP Tool 直接调用 Service，需要额外关注。

---

## 10. Tenant Isolation 完整验证

### 10.1 正面验证（隔离有效）

| 位置 | 机制 | 验证 |
|------|------|------|
| `get_current_user()` auth.py:27 | set_tenant_id from JWT | ✅ 注入 |
| `TenantASGIMiddleware` line:94 | set_tenant_id from header | ✅ 注入 |
| `TenantAwareRepository.create()` line:437 | 自动注入 tenant_id | ✅ 写入隔离 |
| `tenant_query.py` do_orm_execute | 自动 WHERE tenant_id | ✅ 查询隔离 |
| `BookingRepository.get_by_id()` 继承 | 自动 tenant 检查 | ✅ 单条隔离 |
| `BookingRepository.search()` line:68-71 | 手动 tenant 过滤 | ✅ 列表隔离 |

### 10.2 SKIP_TENANT_PATHS 风险

`tenant_middleware.py:36`：

```python
SKIP_TENANT_PATHS = [
    "/docs", ...,
    "/api/v1/courses",   # ⚠️ 课程列表跳过租户中间件
]
```

- 但 courses 路由仍有 `get_current_user` 依赖（JWT 包含 tenant_id），所以**实际上 tenant_id 还是会从 auth.py 设置到 ContextVar**
- 不过如果 `/api/v1/courses` 有某些端点**不要求认证**，则可能泄露数据

### 10.3 UNKNOWN 项

- UNKNOWN: `/api/v1/courses` 的完整端点列表是否有公开且无 auth 的端点

---

## 11. 数据查询汇总

### 11.1 create_booking 涉及的所有 SQL（含隐式）

| # | 触发点 | SQL 类型 | 锁 |
|---|--------|---------|-----|
| 1 | service.py:60 `schedule_repo.get_by_id()` | SELECT course_schedules WHERE id=? | 无 |
| 2 | service.py:84 `find_active_booking()` | SELECT bookings WHERE schedule_id=? AND student_id=? AND status IN (1,3,4) AND tenant_id=? | 无 |
| 3 | repo.py:175-185 `increment_booked_count()` | SELECT course_schedules WHERE id=? AND status=1 AND booked_count<capacity FOR UPDATE | ✅ FOR UPDATE |
| 4 | repo.py:190 | UPDATE (set booked_count=?) | 同事务 |
| 5 | service.py:105 `repo.create()` | INSERT bookings | 无 |
| 6 | BaseRepository | **COMMIT 1** | — |
| 7 | deduc_credit: `get_card_with_lock()` | SELECT membership_cards WHERE id=? AND tenant_id=? FOR UPDATE | ✅ FOR UPDATE |
| 8 | deduc_credit | UPDATE (set used_credits+=1) | 同事务 |
| 9 | deduc_credit | INSERT membership_card_transactions | 同事务 |
| 10 | service.py:122 | **COMMIT 2** | — |

### 11.2 隐式 tenant_query 注入的额外 WHERE

所有 ORM SELECT 都会被 `tenant_query.py` 的 `do_orm_execute` 拦截，自动添加 `WHERE entity.tenant_id = :current_tenant_id`。

但 BookingRepository 的自定义方法（search, find_active_booking 等）已经**手动**加了 tenant_id 过滤。这意味着：
- **双重过滤**（自动 + 手动）— 不会错误但冗余
- 或者 tenant_query.py 的自动注入**可能被手动指定覆盖**（需验证 SQLAlchemy 行为）

---

## 12. 问题清单汇总

| # | 严重度 | 问题 | 位置 | 建议 |
|---|--------|------|------|------|
| P0 | 🔴 Critical | `BaseRepository.create(auto_commit=True)` 导致 Booking 在会员卡扣次**之前**持久化，破坏事务原子性 | `booking/service.py:105` + `base_repository.py:164` | 调用时显式传 `auto_commit=False` |
| P1 | 🟡 Medium | `increment_booked_count` 缺少 `skip_locked=True`，高并发时请求排队 | `schedule/repository.py:182` | 加 `skip_locked=True` |
| P2 | 🟡 Medium | 约课相关路由缺少 `@require_permissions` 装饰器，修复 BYPASS 后可能需要细粒度控制 | `booking/router.py:22-175` | 为 create/cancel 加 `booking:create`，check_in/complete 已有 |
| P3 | 🟡 Medium | `PERMISSION_CHECK_BYPASS=True` 全局绕过 RBAC | `rbac/checker.py:39` | 生产环境改为 False |
| P4 | 🟡 Medium | BookingRepository 自定义方法手动加 tenant_id，绕过 TenantAwareRepository 基类的覆盖 | `booking/repository.py:66-71` 等 | 改为调用基类方法 |
| P5 | 🟢 Low | Token 黑名单功能已实现（`deps/auth.py:_redis_client`）但未在 `decode_token` 中检查 | `core/security.py` | 在 decode 后查 Redis 黑名单 |
| P6 | 🟢 Low | Rate Limit 中间件已定义但未注册 | `main.py:177-181` | lifespan 中 add_middleware |
| P7 | 🟢 Low | 同一学员重复约同一排期失败时返回数据库 ConstraintViolationError 而非友好业务错误 | `booking/service.py:84-86` | 提前检查 + 友好错误消息 |
| P8 | 🟢 Low | BookingService 内部直接 `from app.modules.tenant.service import TenantService`（line 186），应注入依赖 | `booking/service.py:186` | 构造器注入 |

---

## 13. UNKNOWN 项

| # | 项目 | 为什么未知 | 验证方式 |
|---|------|-----------|----------|
| U-01 | `/api/v1/courses` 的完整端点列表中是否有公开端点 | 需要完整 grep courses/router.py 看哪些端点有 get_current_user 依赖 | 读 `modules/course/router.py` |
| U-02 | TenantASGIMiddleware 和 Auth 中都设置了 set_tenant_id，后者是否覆盖前者 | 两者用同一 ContextVar，后调用的覆盖前面的。Auth 肯定在 Router 中最后被调用，所以以 Auth 为准 | 时序分析 |
| U-03 | MembershipCardTransaction 的 idempotency_key 唯一约束 | 只在代码中查，不知道 DB 是否也有唯一索引 | 看 alembic migration |
| U-04 | AI Agent Runtime 是否调用 HTTP API 还是直接 import Service | AI 层实现变化快 | 读 `ai/agent/runtime.py` |
| U-05 | 前端是否有"约课中"按钮防重复提交 | 不在本次后端分析范围 | 看前端代码 |
| U-06 | `schedule.booked_count` 的更新是否有 DB Trigger 做二次保护 | 只看到 CHECK 约束，没看到 Trigger | grep alembic 或 pg_trigger |
| U-07 | 约课 API 是否有 Rate Limit 保护 | 中间件定义了但未注册，不确定是否有其他地方保护 | 全局 grep |
| U-08 | `tenant_query.py` 的 ORM 自动注入和 Repository 手动注入是否冲突 | SQLAlchemy 行为需要测试 | 写集成测试观察生成的 SQL |

---

## 14. 总结

### Backend Agent 对学生约课的完整理解

✅ **路由层**：POST `/api/v1/bookings`，依赖 `get_current_user`，无 RBAC 装饰器  
✅ **Schema 层**：`BookingCreate(schedule_id, source, membership_card_id?)`，纯类型校验  
✅ **Service 层**：`BookingService.create_booking()` 包含全部 7 项业务校验  
✅ **Repository 层**：继承 `TenantAwareRepository`，自定义方法手动加 tenant 过滤  
✅ **Model 层**：`Booking` 有 Partial UNIQUE 保护，`CourseSchedule` 有 CHECK 约束  
✅ **Auth 层**：JWT → set ContextVar（tenant_id, user_id, role_id）  
✅ **RBAC 层**：被 BYPASS=True 完全绕过  
✅ **Tenant 层**：Middleware + Auth + ORM 自动注入 + Repository 手动过滤，四层隔离  
✅ **Redis 层**：RBAC 权限缓存使用，约课流程不直接使用  
✅ **Transaction 层**：**create_booking 有双重 commit 问题**，cancel/check_in/complete 均正确  
✅ **Concurrency 层**：`increment_booked_count` FOR UPDATE 保护，Partial UNIQUE 兜底，**缺少 skip_locked**

### 最关键的发现

1. **Transaction Non-Atomicity（P0）**：BaseRepository.create(auto_commit=True) 在会员卡扣次之前提交 booking，如果扣次失败会留下"幽灵 booking"
2. **RBAC Bypass（P3）**：PERMISSION_CHECK_BYPASS=True 让所有权限检查无效
3. **并发排队（P1）**：increment_booked_count 没有 skip_locked
4. **业务逻辑正确**：7 项业务校验完整、TOCTOU 窗口被 DB UNIQUE 兜底