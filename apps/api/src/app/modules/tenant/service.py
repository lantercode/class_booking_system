"""租户服务 - 配置与基本信息的读写。"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenant.models import Tenant

logger = logging.getLogger(__name__)

# 可被更新的基本信息字段白名单（防止越权写入其他字段）
_UPDATABLE_INFO_FIELDS = ("name", "logo_url", "contact_phone", "contact_email")


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

    async def update_settings(self, db: AsyncSession, tenant_id: int, data: dict) -> dict:
        """更新租户配置

        采用浅合并策略：``data`` 中的键覆盖现有 settings 同名键，
        未在 ``data`` 中出现的键保持不变。

        - tenant_id 取自 current_user 上下文，绝不信任请求体（见 tenant-isolation.md）。
        - 事务边界由 Service 统一提交（见 layering.md / transaction.md）。
        - 返回结构与 ``get_settings`` 一致，便于前端回读。
        """
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()

        if not tenant:
            logger.warning(f"[TenantService] update_settings: tenant {tenant_id} not found")
            return {}

        current = dict(tenant.settings or {})
        # 浅合并：data 覆盖 current 同名键，保留未传键
        merged = {**current, **data}
        # 赋值新 dict 确保 SQLAlchemy 检测到 JSONB 字段变更
        tenant.settings = merged
        await db.commit()

        return {
            "booking_cancel_minutes": merged.get("booking_cancel_minutes", 90),
            "booking_advance_days": merged.get("booking_advance_days", 14),
        }

    async def update_info(self, db: AsyncSession, tenant_id: int, data: dict) -> dict:
        """更新租户基本信息

        仅更新 ``data`` 中非 None 的白名单字段，避免越权写入 status / plan / slug 等。

        - tenant_id 取自 current_user 上下文，绝不信任请求体。
        - 事务边界由 Service 统一提交。
        - 返回结构与 ``get_tenant_info`` 一致。
        """
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()

        if not tenant:
            logger.warning(f"[TenantService] update_info: tenant {tenant_id} not found")
            return {}

        for field in _UPDATABLE_INFO_FIELDS:
            value = data.get(field)
            if value is not None:
                setattr(tenant, field, value)

        await db.commit()

        return {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "logo_url": tenant.logo_url,
            "contact_phone": tenant.contact_phone,
            "contact_email": tenant.contact_email,
        }
