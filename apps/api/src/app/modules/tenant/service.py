from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenant.models import Tenant


class TenantService:
    """租户服务"""

    async def get_settings(self, db: AsyncSession, tenant_id: int) -> dict:
        """获取租户配置"""
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            return {}
        
        # 返回默认配置，如果 settings 中没有则使用默认值
        settings = tenant.settings or {}
        
        return {
            "booking_cancel_minutes": settings.get("booking_cancel_minutes", 90),
            "booking_advance_days": settings.get("booking_advance_days", 14),
        }

    async def get_tenant_info(self, db: AsyncSession, tenant_id: int) -> dict:
        """获取租户基本信息"""
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            return {}
        
        return {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "logo_url": tenant.logo_url,
            "contact_phone": tenant.contact_phone,
            "contact_email": tenant.contact_email,
        }