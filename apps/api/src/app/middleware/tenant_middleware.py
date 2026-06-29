"""
多租户中间件 - 纯 ASGI 实现
避免使用 BaseHTTPMiddleware 以解决 asyncio 事件循环冲突问题
"""

from starlette.types import ASGIApp,Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response


class TenantASGIMiddleware:
    """
    纯 ASGI 多租户中间件

    不继承 BaseHTTPMiddleware，避免创建额外的 Task
    解决 "Future attached to a different loop" 错误
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # 只处理 HTTP 请求
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 创建 Request 对象以访问 headers
        request = Request(scope, receive)

        # 1、请求前：提取并设置租户信息
        current_tenant = request.headers.get("x-tenant-id")
        if current_tenant:
            print(f"[Tenant Middleware] Tenant ID from header: {current_tenant}")
        else:
            print(f"[Tenant Middleware] No tenant header, path: {request.url.path}")

        # 2、调用下一个应用（不创建额外 Task）
        await self.app(scope, receive, send)
