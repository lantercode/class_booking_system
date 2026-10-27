"""Home Config Repository - 首页配置数据访问层"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.core.tenant_context import get_tenant_id
from app.modules.home_config.models import HomeConfig


class HomeConfigRepository(TenantAwareRepository[HomeConfig]):
    """首页配置数据访问层"""

    model_class = HomeConfig

    async def get_latest_published(self, db: AsyncSession) -> HomeConfig | None:
        """获取当前租户最新 published 版本"""
        query = (
            select(HomeConfig)
            .where(HomeConfig.scope == "published")
            .order_by(HomeConfig.version.desc())
            .limit(1)
        )
        # 注意：TenantAwareRepository 的 ORM 事件会自动注入 tenant_id
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_draft(self, db: AsyncSession) -> HomeConfig | None:
        """获取当前租户 draft（scope=draft, version=1）"""
        query = (
            select(HomeConfig)
            .where(HomeConfig.scope == "draft", HomeConfig.version == 1)
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def list_published_versions(self, db: AsyncSession) -> list[HomeConfig]:
        """获取当前租户所有已发布版本列表（按 version 降序）"""
        query = (
            select(HomeConfig)
            .where(HomeConfig.scope == "published")
            .order_by(HomeConfig.version.desc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())
