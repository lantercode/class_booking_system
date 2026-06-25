"""通用模块路由 - 健康检查等无业务依赖的接口."""
from fastapi import APIRouter, Depends

from app.core.response import success

from app.deps.auth import get_current_user, get_optional_user
from app.core.security import create_access_token

from app.core.exceptions import (
    AuthException,
    ValidationException,
    PermissionException,
    NotFoundException,
    BusinessException,
)
router = APIRouter(prefix="/common", tags=["Common"])


@router.get("/health")
async def health() -> dict:
    """健康检查接口 - T01 验收依据."""
    return success(data={"status": "ok"})

@router.get("/test-exception")
async def test_exception(type: str) -> dict:
    """测试异常接口 - T02 验收依据."""
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

@router.get("/test-auth")
async def test_auth(current_user: dict = Depends(get_current_user)) -> dict:
    return success(data={
        "user_id": current_user.get("user_id"),
        "tenant_id": current_user.get("tenant_id"),
        "message": "认证成功！"
    })

@router.get("/test-token")
async def test_generate_token() -> dict:
    # 生成测试 Token - 用于测试认证依赖
    # 创建一个测试用的 Token payload
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
        "message": "请复制此 Token 用于测试 /test-auth 接口"
    })
