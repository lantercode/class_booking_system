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

当前进度：**T01 验收通过（2026-06-13）**（Monorepo + Docker 基础设施）。
