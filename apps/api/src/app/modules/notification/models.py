from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TenantMixin, TimestampMixin


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(BigInteger)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_audit_tenant_created", "tenant_id", text("created_at DESC")),
        Index("idx_audit_user_created", "tenant_id", "user_id", text("created_at DESC")),
    )


class Notification(Base, TenantMixin, TimestampMixin):
    """站内消息（当前仅承载会员续费预警）。

    幂等：同一租户内 ``idempotency_key`` 唯一，重复投递不会产生第二条消息。
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="接收人用户ID")
    type: Mapped[str] = mapped_column(String(30), nullable=False, comment="消息类型")
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_notifications_tenant_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
        ),
        Index(
            "idx_notifications_user_created",
            "tenant_id",
            "user_id",
            text("created_at DESC"),
        ),
    )
