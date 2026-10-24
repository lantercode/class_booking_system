"""租户管理路由 - 配置与基本信息的读写。

遵守 layering.md：Router 只做参数提取、Pydantic 校验与 Service 调用，
不包含任何业务判断或状态流转。
"""

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.rbac import require_roles
from app.core.response import success
from app.deps.auth import get_current_user
from app.modules.tenant.schemas import (
    TenantInfoUpdate,
    TenantSettingsUpdate,
)
from app.modules.tenant.service import TenantService

router = APIRouter(prefix="/tenant", tags=["租户管理"])

tenant_service = TenantService()


@router.get("/settings", response_model=dict, summary="获取租户配置")
@require_roles("admin", "super_admin")
async def get_tenant_settings(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取当前租户的配置信息"""
    tenant_id = current_user.get("tenant_id")
    settings = await tenant_service.get_settings(db, tenant_id)
    return success(data=settings)


@router.put("/settings", response_model=dict, summary="更新租户配置")
@require_roles("admin", "super_admin")
async def update_tenant_settings(
    payload: TenantSettingsUpdate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """更新当前租户的配置信息（浅合并：保留未传键）"""
    tenant_id = current_user.get("tenant_id")
    # exclude_unset=True：仅传递客户端显式提交的字段，保证浅合并语义
    update_data = payload.model_dump(exclude_unset=True)
    settings = await tenant_service.update_settings(db, tenant_id, update_data)
    return success(data=settings)


@router.get("/info", response_model=dict, summary="获取租户基本信息")
async def get_tenant_info(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取当前租户的基本信息（名称、logo等）"""
    tenant_id = current_user.get("tenant_id")
    info = await tenant_service.get_tenant_info(db, tenant_id)
    return success(data=info)


@router.put("/info", response_model=dict, summary="更新租户基本信息")
@require_roles("admin", "super_admin")
async def update_tenant_info(
    payload: TenantInfoUpdate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """更新当前租户的基本信息（名称、logo、联系方式）"""
    tenant_id = current_user.get("tenant_id")
    update_data = payload.model_dump(exclude_unset=True)
    info = await tenant_service.update_info(db, tenant_id, update_data)
    return success(data=info)
