"""认证模块路由 - 注册、登录、登出、刷新 Token、微信登录."""

from fastapi import APIRouter, Depends, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.database import get_session
from app.deps.auth import get_current_user, get_redis_client
from app.core.exceptions import ValidationException
from app.modules.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    AuthResponse,
    TokenResponse,
    UserResponse,
    WechatLoginRequest,
    WechatBindRequest,
    WechatLoginResponse,
)
from app.modules.auth.service import AuthService


router = APIRouter(prefix="/auth", tags=["认证管理"])


# ============================================================
# 账号密码认证
# ============================================================

@router.post(
    "/register",
    status_code=201,
    summary="用户注册",
    description="创建新用户账号，返回访问令牌和刷新令牌",
    responses={
        201: {"description": "注册成功", "model": AuthResponse},
        400: {"description": "手机号已存在或租户不存在"},
    },
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """用户注册 - 创建账号并获取 Token"""
    result = await AuthService.register(db, data)
    return success(data=result, msg="注册成功")


@router.post(
    "/login",
    summary="用户登录",
    description="通过手机号密码登录，返回双Token（access_token + refresh_token）",
    responses={
        200: {"description": "登录成功", "model": AuthResponse},
        401: {"description": "手机号或密码错误"},
        403: {"description": "账号已被禁用"},
    },
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """用户登录 - 获取访问令牌"""
    result = await AuthService.login(db, data)
    return success(data=result, msg="登录成功")


@router.post(
    "/logout",
    summary="用户登出",
    description="吊销当前用户的 refresh_token，使其无法继续使用",
    responses={
        200: {"description": "登出成功"},
    },
)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    redis_client=Depends(get_redis_client),
) -> dict:
    """用户登出 - 吊销Token"""
    # 安全地获取 refresh_token（可选参数）
    try:
        body = await request.json()
        refresh_token = body.get("refresh_token")
    except Exception:
        refresh_token = None

    # 如果提供了 refresh_token，将其加入黑名单
    if refresh_token:
        await AuthService.logout(
            db,
            current_user["user_id"],
            refresh_token,
            redis_client,
        )

    return success(msg="登出成功")


@router.post(
    "/refresh-token",
    summary="刷新令牌",
    description="使用 refresh_token 获取新的 access_token 和 refresh_token（一次性使用）",
    responses={
        200: {"description": "刷新成功", "model": TokenResponse},
        401: {"description": "Token无效或已过期"},
        403: {"description": "Token已被吊销"},
    },
)
async def refresh_token_endpoint(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_session),
    redis_client=Depends(get_redis_client),
) -> dict:
    """刷新Token - 获取新的双Token"""
    result = await AuthService.refresh_token(
        db,
        data.refresh_token,
        redis_client,
    )
    return success(data=result, msg="Token 刷新成功")


# ============================================================
# 当前用户
# ============================================================

@router.get(
    "/me",
    summary="获取当前用户",
    description="根据当前Token获取登录用户的基本信息",
    responses={
        200: {"description": "获取成功", "model": UserResponse},
    },
)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """获取当前用户信息"""
    user = await AuthService.get_current_user_profile(db, current_user["user_id"])
    return success(data=user)


@router.patch(
    "/me",
    summary="更新当前用户信息",
    description="更新当前登录用户的个人信息（仅允许修改昵称和头像）",
    responses={
        200: {"description": "更新成功", "model": UserResponse},
        400: {"description": "没有可更新的字段"},
    },
)
async def update_me(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """更新当前用户信息（学员端）"""
    user = await AuthService.update_current_user_profile(
        db, current_user["user_id"], data,
    )
    return success(data=user, msg="个人信息更新成功")


# ============================================================
# 微信登录
# ============================================================

@router.post(
    "/wechat-auto-login",
    summary="微信自动登录",
    description="通过微信 code 自动登录，已绑定用户直接返回 Token，未绑定返回 bind_token",
    responses={
        200: {"description": "登录成功", "model": WechatLoginResponse},
        401: {"description": "微信登录失败"},
        403: {"description": "账号已被禁用"},
    },
)
async def wechat_auto_login(
    data: WechatLoginRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """微信自动登录 - code 换取 openid 并检查绑定状态"""
    result = await AuthService.wechat_auto_login(
        db, data.code, data.app_id, data.tenant_slug,
    )
    return success(data=result, msg="登录成功")


@router.post(
    "/wechat-login",
    summary="微信绑定登录",
    description="通过 bind_token 和加密手机号/手动输入手机号绑定微信账号，完成登录",
    responses={
        200: {"description": "绑定成功 / 手机号未注册", "model": WechatLoginResponse},
        401: {"description": "绑定凭证无效或已过期"},
        403: {"description": "账号已被禁用"},
    },
)
async def wechat_login(
    data: WechatBindRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """微信绑定 - 支持微信授权手机号解密或手动输入"""
    result = await AuthService.wechat_bind(
        db,
        bind_token=data.bind_token,
        phone=data.phone,
        encrypted_data=data.encrypted_data,
        iv=data.iv,
        tenant_slug=data.tenant_slug,
    )
    if result.need_bind:
        return success(data=result, msg=result.error_msg or "绑定失败")
    return success(data=result, msg="绑定成功")