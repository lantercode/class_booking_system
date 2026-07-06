"""
User Router - 用户管理路由

提供用户管理的 REST API 接口，包含：
- 用户 CRUD
- 密码管理
- 角色绑定
"""

from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.database import get_session
from app.deps.auth import get_current_user, get_redis_client
from app.core.rbac import require_permissions

from app.modules.user.schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    ChangePasswordRequest,
)
from app.modules.user.service import UserService

router = APIRouter(prefix="/users", tags=["用户管理"])
user_service = UserService()


# ==================== 用户 CRUD ====================

@router.post(
    "",
    response_model=dict,
    status_code=201,
    summary="创建用户",
    description="创建新用户账号（需 user:create 权限）",
)
@require_permissions("user:create")
async def create_user(
    data: UserCreate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """创建用户接口"""
    result = await user_service.create_user(
        db,
        data,
        operator_id=current_user.get("user_id"),
    )
    return success(data=result, msg="用户创建成功")


@router.get(
    "",
    response_model=dict,
    summary="获取用户列表",
    description="分页获取用户列表（支持关键词搜索和状态筛选，需 user:read 权限）",
)
@require_permissions("user:read")
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str = Query(None, description="搜索关键词（手机号/昵称/姓名）"),
    status: int = Query(None, ge=0, le=1, description="状态筛选：0禁用/1启用"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取用户列表"""
    result = await user_service.list_users(
        db,
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.get(
    "/{user_id}",
    response_model=dict,
    summary="获取用户详情",
    description="获取指定用户的详细信息（需 user:read 权限）",
)
@require_permissions("user:read")
async def get_user(
    user_id: int = Path(..., description="用户ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取用户详情"""
    result = await user_service.get_user_by_id(db, user_id)
    return success(data=result)


@router.patch(
    "/{user_id}",
    response_model=dict,
    summary="更新用户信息",
    description="更新用户信息（需 user:update 权限）",
)
@require_permissions("user:update")
async def update_user(
    user_id: int = Path(..., description="用户ID"),
    data: UserUpdate = Body(...),
    db: AsyncSession = Depends(get_session),
    redis_client=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """更新用户信息"""
    result = await user_service.update_user(
        db,
        user_id,
        data,
        redis_client=redis_client,
    )
    return success(data=result, msg="用户信息更新成功")


@router.delete(
    "/{user_id}",
    response_model=dict,
    summary="删除用户",
    description="软删除用户（需 user:delete 权限，不能删除自己）",
)
@require_permissions("user:delete")
async def delete_user(
    user_id: int = Path(..., description="用户ID"),
    db: AsyncSession = Depends(get_session),
    redis_client=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """删除用户"""
    await user_service.delete_user(
        db,
        user_id,
        operator_id=current_user.get("user_id"),
        redis_client=redis_client,
    )
    return success(msg="用户删除成功")


# ==================== 密码管理 ====================

@router.post(
    "/{user_id}/password/change",
    response_model=dict,
    summary="修改密码",
    description="用户自己修改密码（需提供旧密码）",
)
async def change_password(
    user_id: int = Path(..., description="用户ID"),
    data: ChangePasswordRequest = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """修改密码（用户自己操作）
    
    注意：用户只能修改自己的密码，user_id 必须与当前登录用户一致
    """
    # 验证只能修改自己的密码
    if user_id != current_user.get("user_id"):
        from app.core.exceptions import AuthException
        raise AuthException("只能修改自己的密码")
    
    await user_service.change_password(db, user_id, data)
    return success(msg="密码修改成功，请重新登录")


@router.post(
    "/{user_id}/password/reset",
    response_model=dict,
    summary="重置密码",
    description="管理员重置用户密码（需 user:reset_password 权限）",
)
@require_permissions("user:reset_password")
async def reset_password(
    user_id: int = Path(..., description="用户ID"),
    new_password: str = Body(..., embed=True, description="新密码"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """重置用户密码（管理员操作）"""
    await user_service.reset_password(
        db,
        user_id,
        new_password,
        operator_id=current_user.get("user_id"),
    )
    return success(msg="密码重置成功")


# ==================== 角色管理 ====================

@router.get(
    "/{user_id}/roles",
    response_model=dict,
    summary="获取用户角色",
    description="获取指定用户的角色列表（需 user:read 权限）",
)
@require_permissions("user:read")
async def get_user_roles(
    user_id: int = Path(..., description="用户ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取用户角色列表"""
    result = await user_service.get_user_roles(db, user_id)
    return success(data=result)


@router.put(
    "/{user_id}/roles",
    response_model=dict,
    summary="分配用户角色",
    description="为用户分配角色（覆盖式，需 role:assign 权限）",
)
@require_permissions("role:assign")
async def assign_user_roles(
    user_id: int = Path(..., description="用户ID"),
    role_ids: list[int] = Body(..., description="角色ID列表"),
    db: AsyncSession = Depends(get_session),
    redis_client=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """分配用户角色"""
    await user_service.assign_roles(
        db,
        user_id,
        role_ids,
        redis_client=redis_client,
    )
    return success(msg="角色分配成功")