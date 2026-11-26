"""站内消息服务：创建（幂等）、列表、已读；以及审计日志写入。"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notification.models import AuditLog
from app.modules.notification.repository import NotificationRepository


class NotificationService:
    def __init__(self) -> None:
        self.repo = NotificationRepository()

    async def create_idempotent(
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
        """创建站内消息；幂等键冲突时返回 None（不抛异常）。"""
        return await self.repo.create_if_absent(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            type=type,
            title=title,
            content=content,
            idempotency_key=idempotency_key,
        )

    async def list_for_user(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        rows, total = await self.repo.list_for_user(
            db, tenant_id=tenant_id, user_id=user_id, page=page, page_size=page_size
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": item.id,
                    "type": item.type,
                    "title": item.title,
                    "content": item.content,
                    "read": item.read_at is not None,
                    "created_at": item.created_at.isoformat(),
                }
                for item in rows
            ],
        }

    async def mark_read(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        user_id: int,
        notification_id: int,
    ) -> bool:
        return await self.repo.mark_read(
            db, tenant_id=tenant_id, user_id=user_id, notification_id=notification_id
        )

    async def count_today(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        type: str,
    ) -> int:
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.repo.count_since(
            db, tenant_id=tenant_id, type=type, since=today_start
        )


notification_service = NotificationService()


async def record_audit(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """写入审计日志（who / what / when / 结果 / 确认来源由调用方放进 payload）。"""
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            ip=ip,
            user_agent=user_agent,
        )
    )
