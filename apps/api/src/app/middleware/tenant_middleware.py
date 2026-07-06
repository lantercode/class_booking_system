"""
多租户中间件 - 纯 ASGI 实现

功能：
- 从请求头提取租户信息（x-tenant-id 或 x-tenant-slug）
- 设置到 ContextVar（供后续业务逻辑使用）
- 支持跳过特定路径（如 /health, /docs）
- 避免 BaseHTTPMiddleware 的 asyncio 冲突问题
"""

import logging
from typing import Optional

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.tenant_context import (
    set_tenant_id,
    set_user_id,
    get_tenant_id,
)

logger = logging.getLogger(__name__)

# 跳过租户检查的路径前缀
SKIP_TENANT_PATHS = [
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/common/health",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/me",
    "/api/v1/courses",
]


class TenantASGIMiddleware:
    """
    纯 ASGI 多租户中间件

    特性：
    - 从 Header 提取租户信息并注入 ContextVar
    - 支持 x-tenant-id (数字) 和 x-tenant-slug (字符串)
    - 自动跳过公开接口（无需认证的路径）
    - 不继承 BaseHTTPMiddleware，无异步冲突
    """

    def __init__(self, app: ASGIApp, session_factory=None):
        self.app = app
        self.session_factory = session_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # 只处理 HTTP 请求
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 创建 Request 对象以访问 headers
        request = Request(scope, receive)
        path = request.url.path

        # 检查是否需要跳过租户验证
        if self._should_skip_tenant(path):
            logger.debug(f"[Tenant Middleware] Skip tenant check for: {path}")
            await self.app(scope, receive, send)
            return

        # 提取租户信息
        tenant_id = await self._extract_tenant(request)

        if not tenant_id:
            # 无租户信息 → 返回错误或使用默认值
            logger.warning(f"[Tenant Middleware] No tenant info for: {path}")
            response = JSONResponse(
                status_code=400,
                content={
                    "code": 40001,
                    "msg": "缺少租户信息，请提供 x-tenant-id 或 x-tenant-slug",
                    "data": None
                }
            )
            await response(scope, receive, send)
            return

        # 设置到 ContextVar
        set_tenant_id(tenant_id)
        logger.info(f"[Tenant Middleware] Set tenant_id={tenant_id} for: {path}")

        # 调用下一个应用
        try:
            await self.app(scope, receive, send)
        finally:
            # 清理 ContextVar（可选）
            set_tenant_id(None)

    def _should_skip_tenant(self, path: str) -> bool:
        """判断是否跳过租户验证"""
        for skip_path in SKIP_TENANT_PATHS:
            if path.startswith(skip_path):
                return True
        return False

    async def _extract_tenant(self, request: Request) -> Optional[int]:
        """
        从请求头提取租户 ID

        支持两种格式：
        1. x-tenant-id: 10 (直接提供数字 ID)
        2. x-tenant-slug: dance-school (提供 slug，需查询数据库)
        """
        # 方式 1：直接提供 tenant_id
        tenant_id_header = request.headers.get("x-tenant-id")
        if tenant_id_header:
            try:
                return int(tenant_id_header)
            except ValueError:
                logger.error(f"[Tenant Middleware] Invalid x-tenant-id: {tenant_id_header}")
                return None

        # 方式 2：通过 slug 查询
        tenant_slug = request.headers.get("x-tenant-slug")
        if tenant_slug:
            result = await self._get_tenant_by_slug(tenant_slug)
            if result:
                tenant_id, status = result

                # 校验租户状态
                from app.modules.tenant.models import TenantStatus
                if status != TenantStatus.ACTIVE.value:
                    logger.error(f"[Tenant Middleware] Tenant {tenant_slug} is disabled")
                    return None
                return tenant_id
            else:
                logger.error(f"[Tenant Middleware] Tenant {tenant_slug} not found")
                return None

        return None

    async def _get_tenant_by_slug(self, slug: str):
        """
        通过 slug 查询租户

        Returns:
            (tenant_id, status) 元组，如果找不到返回 None
        """
        if not self.session_factory:
            logger.error("[Tenant Middleware] SessionFactory not configured")
            return None

        from sqlalchemy import select
        from app.modules.tenant.models import Tenant

        async with self.session_factory() as session:
            result = await session.execute(select(Tenant.id, Tenant.status).where(Tenant.slug == slug))
            tenant = result.first()

            if tenant:
                return  (tenant.id, tenant.status)
            return None