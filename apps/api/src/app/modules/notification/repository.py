"""站内消息数据访问层。"""

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.notification.models import Notification


class NotificationRepository(TenantAwareRepository[Notification]):
    model_class = Notification

    async def create_if_absent(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        user_id: int,
        type: str,
        title: str,
        content: str,
        idempotency_key: str,
    ) -> int | None:
        """按 (tenant_id, idempotency_key) 幂等插入；重复时返回 None。"""
        stmt = (
            pg_insert(Notification)
            .values(
                tenant_id=tenant_id,
                user_id=user_id,
                type=type,
                title=title,
                content=content,
                idempotency_key=idempotency_key,
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "idempotency_key"])
            .returning(Notification.id)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Notification], int]:
        base = select(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
        )
        total = (
            await db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            (
                await db.execute(
                    base.order_by(Notification.created_at.desc(), Notification.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    async def mark_read(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        user_id: int,
        notification_id: int,
    ) -> bool:
        result = await db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(UTC))
        )
        return bool(result.rowcount)

    async def count_since(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        type: str,
        since: datetime,
    ) -> int:
        return (
            await db.execute(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.tenant_id == tenant_id,
                    Notification.type == type,
                    Notification.created_at >= since,
                )
            )
        ).scalar_one()
