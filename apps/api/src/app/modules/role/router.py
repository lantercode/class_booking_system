"""
Role Router - 角色权限管理路由

提供角色和权限管理的 REST API 接口，包含：
- 角色 CRUD
- 权限查询
- 角色-权限绑定
"""

from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.database import get_session
from app.deps.auth import get_current_user, get_redis_client
from app.core.rbac import require_permissions

from app.modules.role.schemas import (
    RoleCreate,
    RoleUpdate,
    AssignPermissionsRequest,
)
from app.modules.role.service import RoleService

router = APIRouter(prefix="/roles", tags=["角色权限管理"])
role_service = RoleService()


# ==================== 角色 CRUD ====================

@router.post(
    "",
    response_model=dict,
    status_code=201,
    summary="创建角色",
    description="创建新角色（需 role:create 权限）",
)
@require_permissions("role:create")
async def create_role(
    data: RoleCreate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """创建角色接口"""
    result = await role_service.create_role(db, data)
    return success(data=result, msg="角色创建成功")


@router.get(
    "",
    response_model=dict,
    summary="获取角色列表",
    description="分页获取角色列表（支持关键词搜索，需 role:read 权限）",
)
@require_permissions("role:read")
async def list_roles(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str = Query(None, description="搜索关键词（代码/名称）"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取角色列表"""
    result = await role_service.list_roles(
        db,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


# ==================== 权限管理 ====================

@router.get(
    "/permissions",
    response_model=dict,
    summary="获取权限列表",
    description="获取所有权限列表（支持按模块筛选，需 role:read 权限）",
)
@require_permissions("role:read")
async def list_permissions(
    module: str = Query(None, description="模块筛选"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取权限列表"""
    result = await role_service.list_permissions(db, module=module)
    return success(data=result)


@router.get(
    "/{role_id}/permissions",
    response_model=dict,
    summary="获取角色权限",
    description="获取指定角色的权限列表（需 role:read 权限）",
)
@require_permissions("role:read")
async def get_role_permissions(
    role_id: int = Path(..., description="角色ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取角色的权限列表"""
    result = await role_service.get_role_permissions(db, role_id)
    return success(data=result)


@router.put(
    "/{role_id}/permissions",
    response_model=dict,
    summary="分配角色权限",
    description="为角色分配权限（覆盖式，需 role:assign 权限）",
)
@require_permissions("role:assign")
async def assign_role_permissions(
    role_id: int = Path(..., description="角色ID"),
    data: AssignPermissionsRequest = Body(...),
    db: AsyncSession = Depends(get_session),
    redis_client=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """分配角色权限"""
    await role_service.assign_permissions(
        db,
        role_id,
        data.permission_ids,
        redis_client=redis_client,
    )
    return success(msg="权限分配成功")


@router.get(
    "/{role_id}",
    response_model=dict,
    summary="获取角色详情",
    description="获取指定角色的详细信息（需 role:read 权限）",
)
@require_permissions("role:read")
async def get_role(
    role_id: int = Path(..., description="角色ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取角色详情"""
    result = await role_service.get_role_by_id(db, role_id)
    return success(data=result)


@router.patch(
    "/{role_id}",
    response_model=dict,
    summary="更新角色",
    description="更新角色信息（需 role:update 权限，不能修改系统角色）",
)
@require_permissions("role:update")
async def update_role(
    role_id: int = Path(..., description="角色ID"),
    data: RoleUpdate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """更新角色信息"""
    result = await role_service.update_role(db, role_id, data)
    return success(data=result, msg="角色更新成功")


@router.delete(
    "/{role_id}",
    response_model=dict,
    summary="删除角色",
    description="删除角色（需 role:delete 权限，不能删除系统角色）",
)
@require_permissions("role:delete")
async def delete_role(
    role_id: int = Path(..., description="角色ID"),
    db: AsyncSession = Depends(get_session),
    redis_client=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """删除角色"""
    await role_service.delete_role(db, role_id, redis_client=redis_client)
    return success(msg="角色删除成功")