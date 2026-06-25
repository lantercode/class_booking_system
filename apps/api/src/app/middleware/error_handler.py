from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import DanceSaasException
from app.core.response import fail

async def dance_saas_exception_handler(request: Request, exc: DanceSaasException) -> JSONResponse:
    """
    全局异常处理器 - 统一处理所有业务异常
    
    Args:
        request: FastAPI 请求对象
        exc: 抛出的异常实例
        
    Returns:
        统一格式的错误响应 JSON
    """
    # 将 list[str] 转换为 list[dict] 格式（符合 fail() 函数要求）
    errors = [{"msg": e} for e in exc.errors]
    
    # 调用 fail() 函数生成统一响应格式
    info = fail(code=exc.code, msg=exc.msg, errors=errors)
    
    # 返回 JSONResponse，HTTP 状态码与业务错误码一致
    return JSONResponse(status_code=exc.code, content=info)