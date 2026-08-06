"""通用模块路由 - 健康检查等无业务依赖的接口."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.response import success
from app.deps.auth import get_current_user, get_optional_user, get_redis_client
from app.core.security import create_access_token
from app.core.exceptions import (
    AuthException,
    ValidationException,
    PermissionException,
    NotFoundException,
    BusinessException,
)


router = APIRouter(prefix="/common", tags=["Common"])


# ============================================================
# 健康检查与测试
# ============================================================

@router.get(
    "/health",
    summary="健康检查",
    description="检查服务运行状态和 Redis 连接",
)
async def health() -> dict:
    """健康检查接口"""
    redis_client = await get_redis_client()

    status = {
        "status": "healthy" if redis_client else "degraded",
        "redis": "connected" if redis_client else "disconnected",
    }
    if not redis_client:
        status["status"] = "unhealthy"
        raise HTTPException(503, detail=status)

    return status


@router.get(
    "/test-exception",
    summary="测试异常",
    description="测试各类异常处理",
)
async def test_exception(type: str) -> dict:
    """测试异常接口"""
    if type == "auth":
        raise AuthException()
    elif type == "validation":
        raise ValidationException()
    elif type == "permission":
        raise PermissionException()
    elif type == "not_found":
        raise NotFoundException()
    elif type == "business":
        raise BusinessException()
    else:
        return success(msg=f"未知类型：{type}")


@router.get(
    "/test-auth",
    summary="测试认证",
    description="测试认证依赖注入",
)
async def test_auth(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """测试认证接口"""
    return success(data={
        "user_id": current_user.get("user_id"),
        "tenant_id": current_user.get("tenant_id"),
        "message": "认证成功！",
    })


@router.get(
    "/test-token",
    summary="生成测试 Token",
    description="创建一个测试用的 Token，用于测试认证依赖",
)
async def test_generate_token() -> dict:
    """生成测试 Token"""
    payload = {
        "user_id": 1,
        "tenant_id": 10,
        "platform_role": "admin",
        "role_codes": ["teacher", "student"],
    }
    token = create_access_token(payload)
    return success(data={
        "token": token,
        "payload": payload,
        "message": "请复制此 Token 用于测试 /test-auth 接口",
    })