from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.deps.auth import get_current_user
from app.core.response import success
from app.modules.tenant.service import TenantService

router = APIRouter(prefix="/tenant", tags=["租户管理"])

tenant_service = TenantService()


@router.get("/settings", response_model=dict, summary="获取租户配置")
async def get_tenant_settings(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取当前租户的配置信息"""
    tenant_id = current_user.get("tenant_id")
    settings = await tenant_service.get_settings(db, tenant_id)
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