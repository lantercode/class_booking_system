"""FastAPI 应用入口."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.common.router import router as common_router
from app.modules.auth.router import router as auth_router
from app.modules.admin.router import router as admin_router  # ⭐ 新增：管理后台路由
from app.modules.user.router import router as user_router  # ⭐ 新增：用户管理路由
from app.modules.role.router import router as role_router  # ⭐ 新增：角色权限路由
from app.modules.course.router import router as course_router  # ⭐ 新增：课程路由（T05 占位）
from app.modules.classroom.router import router as classroom_router  # ⭐ 新增：教室路由
from app.modules.schedule.router import router as schedule_router  # ⭐ 新增：排期路由
from app.modules.booking.router import router as booking_router  # ⭐ 新增：预约路由

from app.middleware.error_handler import dance_saas_exception_handler
from app.core.exceptions import DanceSaasException
from app.middleware.tenant_middleware import TenantASGIMiddleware

from contextlib import asynccontextmanager
from app.deps.auth import get_redis_client
# from starlette.middleware.sessions import Session

from app.core.database import SessionLocal
from app.core.tenant_query import setup_tenant_query_injection

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器 - 初始化 Redis + 租户注入"""
    # 1. 启用多租户查询自动注入
    setup_tenant_query_injection()
    print("✅ 多租户查询自动注入已启用")

    # 2. 检查并初始化 Redis
    print("检查 Redis 连接...")
    redis_client = await get_redis_client()
    if not redis_client:
        raise RuntimeError(
            "❌ Redis 不可用！生产环境必须启用 Redis。\n"
            "请检查: docker-compose up -d redis"
        )
    print("✅ Redis 连接正常！")

    yield # 应用运行中

    # 关闭时清理
    pass


app = FastAPI(
    title="Dance SaaS API",
    description="舞蹈机构约课 SaaS 系统 API",
    version="0.1.0",
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
)
app.add_exception_handler(DanceSaasException, dance_saas_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ↓↓↓ 在这里添加租户中间件 ↓↓↓
app.add_middleware(
    TenantASGIMiddleware,
    session_factory=SessionLocal
)

# ⭐ 新增：API 限流中间件配置（防止滥用）
# 注意：中间件将在 lifespan 中动态添加（因为 Redis 需要异步初始化）
RATE_LIMIT_CONFIG = {
    "limit": 100,  # 每分钟最多 100 次请求
    "window": 60,  # 时间窗口：60 秒
    "exclude_paths": ["/docs", "/redoc", "/openapi.json", "/health", "/api/v1/common/health"],
}

API_V1_PREFIX = "/api/v1"
app.include_router(common_router, prefix=API_V1_PREFIX)
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(admin_router, prefix=API_V1_PREFIX)  # ⭐ 管理后台路由（含 RBAC 权限控制）
app.include_router(user_router, prefix=API_V1_PREFIX)  # ⭐ 用户管理路由
app.include_router(role_router, prefix=API_V1_PREFIX)  # ⭐ 角色权限路由
app.include_router(course_router, prefix=API_V1_PREFIX)  # ⭐ 课程路由（T05 占位）
app.include_router(classroom_router, prefix=API_V1_PREFIX)  # ⭐ 教室路由
app.include_router(schedule_router, prefix=API_V1_PREFIX)  # ⭐ 排期路由
app.include_router(booking_router, prefix=API_V1_PREFIX)  # ⭐ 预约路由