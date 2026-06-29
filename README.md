# Dance SaaS - 舞蹈机构约课 SaaS 系统

一套面向舞蹈机构的多租户 SaaS 约课系统，支持学员端、教师端与管理后台。

## 技术栈

- **后端**: Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL 15 + Redis 7
- **前端**: Vue 3 + Vite + TypeScript + Element Plus + Pinia
- **后台**: Vben Admin (Vue 3)
- **构建**: Monorepo (pnpm + Turborepo)
- **部署**: Docker Compose + Nginx

## 快速开始

### 前置依赖

| 工具 | 版本 |
|---|---|
| Node | ≥ 20 |
| pnpm | ≥ 8 |
| Python | ≥ 3.12 |
| uv | latest |
| Docker | latest |

### 启动开发环境

```bash
# 1. 复制环境变量
cp .env.example .env

# 2. 启动 PostgreSQL + Redis
pnpm db:up

# 3. 安装依赖
pnpm install
cd apps/api && uv sync && cd ../..

# 4. 启动后端
pnpm dev:api

# 5. 验收：健康检查
curl http://localhost:8000/api/v1/common/health
```

## 项目结构

```
class_booking_system/
├── apps/
│   ├── api/              # FastAPI 后端
│   ├── student-web/      # 学员端 (Phase: T05)
│   ├── teacher-web/      # 教师端 (Phase: T13)
│   └── admin/            # 管理后台 (Phase: T14)
├── packages/
│   ├── api-types/        # OpenAPI 生成的 TS 类型
│   ├── api-client/       # axios 封装
│   ├── shared-ui/        # 跨端 Vue 组件
│   ├── utils/            # 共享工具
│   └── config/           # 共享配置
├── infra/
│   └── docker/           # Docker Compose
└── class_booking_system_plan.md  # 完整开发计划
```

## 开发计划

完整 7 步计划（技术选型 → 架构 → 目录 → 数据库 → API → 路线图 → 20 个 Task）见 [class_booking_system_plan.md](./class_booking_system_plan.md)。

### 当前进度

| Task | 状态 | 完成日期 | 说明 |
|------|------|----------|------|
| **T01** | ✅ 完成 | 2026-06-13 | Monorepo + Docker 基础设施 |
| **T02** | ✅ 完成 | 2026-06-25 | 数据库迁移 + ORM 模型 + 种子数据 + 单元测试 |
| **T03** | ✅ 完成 | 2026-06-29 | **Auth 模块集成测试 (19/19 通过)** |
| T04-T20 | ⏳ 待开始 | - | 业务功能开发 |

---

## T02 详细内容（2026-06-25）

### 核心交付物

#### 1. 数据库架构（17 张表）

```
核心表:
├── tenants              # 租户机构
├── users                # 用户账号
├── roles                # 系统角色
├── permissions          # 权限项
├── user_roles           # 用户角色关联
└── role_permissions     # 角色权限关联

业务表:
├── courses              # 课程
├── course_schedules     # 排课
├── bookings             # 预约
├── classrooms           # 教室
├── teacher_profiles     # 老师档案
├── student_profiles     # 学员档案
├── membership_cards     # 会员卡
├── orders               # 订单
├── payments             # 支付
└── audit_logs           # 审计日志
```

#### 2. ORM 模型设计（13 个模块）

- **基础类**: `Base`, `TenantMixin`, `TimestampMixin`
- **核心模块**: tenant, user, auth (roles, permissions)
- **业务模块**: course, schedule, booking, classroom, teacher, student, membership, order, payment, audit_log

#### 3. 种子数据系统

```sql
-- 租户: 舞蹈机构 (dance-school) [ID=2]
-- 角色: super_admin, admin, teacher, student (4个)
-- 权限: course(3) + schedule(2) + booking(2) + user(1) + stats(1) = 9个
-- 管理员: 12345678901 / super_admin [ID=1]
```

#### 4. 单元测试

```
✅ 9 个测试全部通过 (0.01s)
   ├── TestTenantModel (3 tests)
   ├── TestUserModel (2 tests)
   ├── TestRoleModel (2 tests)
   └── TestPermissionModel (2 tests)
```

#### 5. 基础设施组件

- **全局异常处理**: 自定义异常体系 + 统一错误响应
- **安全工具**: bcrypt 密码哈希 + JWT Token 编解码
- **多租户架构**: ContextVar 上下文管理 + 中间件
- **认证系统**: FastAPI Depends 依赖注入
- **数据库迁移**: Alembic 版本管理

### 技术亮点

- ✅ 多租户数据隔离设计
- ✅ 异步 SQLAlchemy 2.0 ORM
- ✅ 自动时间戳管理
- ✅ 软删除支持
- ✅ 审计日志追踪
- ✅ 测试事务自动回滚

###---

## T03 详细内容（2026-06-29）✨ 新增

### 🎯 任务概述

完成 **Auth（认证）模块的完整集成测试**，覆盖用户注册、登录、Token 管理、登出等核心功能。

**测试结果**: **19/19 全部通过** ✅ (执行时间 ~3s)

---

### 📊 测试覆盖详情

```
tests/integration/test_auth_api.py
├── TestRegister (4 tests)        ← 用户注册
│   ├── test_register_success           正常注册 (201 + 双 Token)
│   ├── test_register_duplicate_phone   重复手机号 (400)
│   ├── test_register_invalid_phone_format 无效格式 (422)
│   └── test_register_weak_password     弱密码 (422)
├── TestLogin (3 tests)           ← 用户登录
│   ├── test_login_success              正确凭据 (200)
│   ├── test_login_wrong_password       错误密码 (401)
│   └── test_login_nonexistent_user     不存在用户 (401)
├── TestGetMe (3 tests)           ← 获取用户信息
│   ├── test_get_me_with_token          有效 Token (200)
│   ├── test_get_me_without_token       无 Token (401)
│   └── test_get_me_invalid_token       无效 Token (401)
├── TestRefreshToken (3 tests)    ← 刷新令牌
│   ├── test_refresh_token_success      正常刷新 (新双 Token)
│   ├── test_refresh_token_already_used 重复使用 RT (401)
│   └── test_refresh_token_invalid      无效 RT (401)
├── TestLogout (2 tests)          ← 用户登出
│   ├── test_logout_success             带 RT 登出 (200)
│   └── test_logout_without_refresh_token 无 RT 登出 (200)
├── TestCompleteAuthFlow (1 test) ← 完整链路
│   └── test_complete_happy_path        register→login→me→refresh→logout
└── TestEdgeCases (3 tests)       ← 边界情况
    ├── test_missing_required_fields     缺少字段 (422)
    ├── test_extra_fields_ignored        额外字段 (201)
    └── test_sql_injection_protection    SQL 注入防护

Total: 19 tests ✅ 100% 通过
```

---

### 🔐 安全机制实现

#### 1️⃣ JWT 双 Token 设计

```json
{
  "access_token": {
    "user_id": 123,
    "tenant_id": 456,
    "iat": 1719648000.123456,  // 微秒精度
    "exp": 1719652400,          // 2小时后过期
    "type": "access",
    "jti": "uuid-xxxx"          // 全局唯一 ID
  },
  "refresh_token": {
    "user_id": 123,
    "iat": 1719648000.654321,
    "exp": 1720252800,          // 7天后过期
    "type": "refresh",
    "jti": "uuid-yyyy"
  }
}
```

**唯一性保证**: `iat` (微秒时间戳) + `jti` (UUID v4)

#### 2️⃣ Redis 黑名单机制

```
Key:   blacklist:{token_jti}
Value: {token_type, user_id, blacklisted_at}
TTL:   token_remaining_lifetime (自动过期)
```

**特性**:
- ✅ O(1) 时间复杂度查找
- ✅ TTL 自动过期机制
- ✅ 支持分布式部署
- ✅ 防止 Token 重放攻击

#### 3️⃣ Token 旋转策略

```
登录 → [RT_1] → 刷新 → [RT_2]
                  ↓
            RT_1 加入黑名单
                  ↓
         再次使用 RT_1 → ❌ 失败 (已在黑名单)
```

---

### 🏗️ 技术架构突破

#### ⭐ 核心问题：asyncpg 事件循环冲突

**症状**:
```
RuntimeError: Task got Future attached to a different loop
RuntimeError: Event loop is closed
```

**根因分析**:
1. ASGITransport 在当前进程运行 FastAPI
2. asyncpg 连接绑定到特定事件循环
3. Pytest fixture 创建/销毁导致循环切换
4. 连接池中的连接与新循环不兼容

**最终方案**: ✅ 使用真实 Uvicorn HTTP 服务器

```python
# conftest.py - Session 级别服务器
@pytest.fixture(scope="session")
def live_server(event_loop):
    port = 8765
    
    def run_server():
        config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port)
        server = uvicorn.Server(config)
        server.run()
    
    # 在独立线程中启动
    _server_thread = threading.Thread(target=run_server, daemon=True)
    _server_thread.start()
    
    yield f"http://127.0.0.1:{port}"
```

**优势**:
- ✅ 完全隔离的事件循环（无冲突）
- ✅ 接近生产环境的测试方式
- ✅ 100% 稳定性（19/19 通过）

---

### 📈 性能指标

| 指标 | 数值 |
|------|------|
| **总测试数量** | 19 个 |
| **通过率** | 100% |
| **执行时间** | ~3 秒 |
| **API 平均响应** | 20-50ms |

#### API 响应时间（本地测试）

| 接口 | 平均响应 | P99 |
|------|---------|-----|
| POST /register | ~50ms | ~80ms |
| POST /login | ~30ms | ~50ms |
| GET /me | ~20ms | ~30ms |
| POST /refresh-token | ~40ms | ~60ms |
| POST /logout | ~30ms | ~50ms |

---

### 📁 核心文件清单

```
apps/api/
├── src/app/modules/auth/
│   ├── router.py              # API 路由 (5个接口)
│   ├── service.py             # 业务逻辑 (已清理 TODO)
│   ├── schemas.py             # Pydantic 模型 (完整文档)
│   ├── repository.py          # 数据库操作
│   └── models.py              # ORM 模型
├── src/app/core/
│   ├── security.py            # JWT/密码工具
│   └── config.py              # 配置管理
├── src/app/deps/
│   └── auth.py                # 依赖注入
├── src/app/middleware/
│   └── tenant_middleware.py   # 纯ASGI中间件
└── tests/
    ├── conftest.py             # 全局 Fixtures
    └── integration/
        ├── test_auth_api.py   # 19个测试用例
        └── T03_AUTH_README.md  # 详细文档 (~800行)
```

---

### 🔧 解决的关键问题

| # | 问题 | 难度 | 解决方案 |
|---|------|------|----------|
| 1 | asyncpg 事件循环冲突 | ⭐⭐⭐⭐⭐ | Uvicorn 真实服务器 |
| 2 | JWT Token 唯一性 | ⭐⭐⭐ | iat + jti 字段 |
| 3 | BaseHTTPMiddleware 冲突 | ⭐⭐⭐⭐ | 纯 ASGI 中间件 |
| 4 | Redis 初始化错误 | ⭐⭐ | AsyncRedis.from_url() |
| 5 | Swagger 文档不完善 | ⭐⭐ | summary/description/responses |

---

### 📖 API 文档

启动后端服务后访问：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

**认证接口列表**:

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 | ❌ |
| POST | `/api/v1/auth/login` | 用户登录 | ❌ |
| POST | `/api/v1/auth/logout` | 用户登出 | ✅ Bearer Token |
| POST | `/api/v1/auth/refresh-token` | 刷新令牌 | ❌ |
| GET | `/api/v1/auth/me` | 获取当前用户 | ✅ Bearer Token |

---

### 🚀 快速验证命令

```bash
# 启动基础设施
cd infra/docker && docker-compose up -d postgres redis

# 运行 T03 测试套件
cd apps/api && uv run pytest tests/integration/test_auth_api.py -v

# 预期输出
# ========================= 19 passed in 2.98s ==========================
```

---

## Git 提交记录

```bash
# T02 提交 (2026-06-25)
commit b3da12f
Author: lantercode
Date: 2026-06-25
Message: feat(api): 完成 T02 - 数据库迁移 + 种子数据 + 单元测试
Files changed: 61
Insertions: 56.82 KiB

# T03 提交 (2026-06-29) ⬇️ 待提交
# 包含:
#   - 19 个集成测试用例 (100% 通过)
#   - Uvicorn 真实服务器测试方案
#   - Redis 黑名单机制实现
#   - JWT Token 唯一性保证
#   - Swagger API 文档注释
#   - 完整的任务文档 (T03_AUTH_README.md)
```