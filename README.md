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
| T03-T20 | ⏳ 待开始 | - | 业务功能开发 |

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

### Git 提交记录

```bash
commit b3da12f
Author: lantercode
Date: 2026-06-25
Message: feat(api): 完成 T02 - 数据库迁移 + 种子数据 + 单元测试

Files changed: 61
Insertions: 56.82 KiB
Branch: main -> main
```