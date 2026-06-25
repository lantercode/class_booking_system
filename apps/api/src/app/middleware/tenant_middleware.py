from fastapi import Request
from app.core.tenant_context import get_tenant_id

async def tenant_middleware(request: Request, call_next):
    """
    多租户中间件 - 在每个请求中设置当前租户上下文
    
    TODO (Step 13): 从 JWT Token 中解析 tenant_id 并设置
    """
    # 1、请求前：提取并设置租户信息
    current_tenant = request.headers.get("x-tenant-id")
    if current_tenant:
        print(f"[Tenant Middleware] Tenant ID from header: {current_tenant}")
    else:
        print(f"[Tenant Middleware] No tenant header, path: {request.url.path}")
    
    # 2、调用下一个中间件/路由处理器
    response = await call_next(request)
    
    # 3、请求后：处理响应结果
    return response