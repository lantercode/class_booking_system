import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError as SQLAIntegrityError

from app.core.exceptions import DanceSaasException
from app.core.response import fail

logger = logging.getLogger(__name__)


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


async def integrity_error_handler(request: Request, exc: SQLAIntegrityError) -> JSONResponse:
    """
    全局 DB 约束异常处理器 - 捕获未被 Service 层处理的 IntegrityError

    当 Service 层未显式捕获 SQLAlchemy IntegrityError 时（例如：
    其他模块的 Repository 操作直接触发唯一约束冲突），此 handler 作为兜底，
    将数据库原始错误转换为友好的 HTTP 409 Conflict 响应。

    Args:
        request: FastAPI 请求对象
        exc: SQLAlchemy IntegrityError 异常

    Returns:
        统一格式的 409 Conflict JSON 响应
    """
    err_msg = str(exc).lower()
    logger.warning(
        f"[IntegrityErrorHandler] DB 约束冲突: path={request.url.path}, error={err_msg[:200]}"
    )

    # 根据约束名称返回不同的友好消息
    # 注意：这里做通用判断，具体约束冲突（如 booking 的 unique）应该在 Service 层优先捕获
    if "duplicate key" in err_msg or "unique" in err_msg:
        friendly_msg = "数据冲突：该记录已存在，请检查是否重复操作"
    elif "foreign key" in err_msg:
        friendly_msg = "数据关联错误：引用的资源不存在"
    elif "check" in err_msg:
        friendly_msg = "数据校验失败：不满足业务约束条件"
    else:
        friendly_msg = "数据约束冲突，请稍后重试"

    info = fail(code=409, msg=friendly_msg, errors=[])
    return JSONResponse(status_code=409, content=info)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局兜底异常处理器 - 捕获所有未被其他 handler 处理的异常

    作为最后一道防线，防止：
    - debug=True 时向客户端泄露 traceback
    - debug=False 时返回 FastAPI 默认的 {"detail":"Internal Server Error"}（非统一信封）

    统一返回 {code: 500, msg: "服务暂时不可用，请稍后重试", request_id: ...} 信封，
    原始异常仅记录到服务端日志，不回传给客户端。

    注意：此 handler 注册在 DanceSaasException / IntegrityError 之后，
    Starlette 按异常 MRO 匹配最具体的 handler，因此不会覆盖上述专用 handler，
    也不会覆盖 FastAPI 内置的 RequestValidationError（422）handler。
    """
    logger.exception(f"[UnhandledException] path={request.url.path}")
    info = fail(code=500, msg="服务暂时不可用，请稍后重试")
    return JSONResponse(status_code=500, content=info)
