"""FastAPI 应用入口."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.common.router import router as common_router
from app.modules.auth.router import router as auth_router
from app.middleware.error_handler import dance_saas_exception_handler
from app.core.exceptions import DanceSaasException
from app.middleware.tenant_middleware import TenantASGIMiddleware

from contextlib import asynccontextmanager
from app.deps.auth import get_redis_client


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器 - 初始化 Redis 连接"""
    # 启动时检查 Redis
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
    TenantASGIMiddleware
)

API_V1_PREFIX = "/api/v1"
app.include_router(common_router, prefix=API_V1_PREFIX)
app.include_router(auth_router,prefix=API_V1_PREFIX)
