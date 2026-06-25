"""FastAPI 应用入口."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.modules.common.router import router as common_router
from app.middleware.error_handler import dance_saas_exception_handler
from app.core.exceptions import DanceSaasException
from app.middleware.tenant_middleware import tenant_middleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


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
    BaseHTTPMiddleware,
    dispatch=tenant_middleware,
)

API_V1_PREFIX = "/api/v1"
app.include_router(common_router, prefix=API_V1_PREFIX)
