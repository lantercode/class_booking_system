from datetime import datetime

from sqlalchemy import BigInteger, String, SmallInteger, Date, DateTime, Index, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4
from enum import Enum

from app.shared.base_model import Base, TimestampMixin, TenantMixin


class GenderStatus(Enum):
    UNKNOWN = 0
    MALE = 1
    FEMALE = 2


class UserStatus(Enum):
    DISABLED = 0
    ACTIVE = 1


class User(Base, TimestampMixin, TenantMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(50))
    real_name: Mapped[str | None] = mapped_column(String(50))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    gender: Mapped[int | None] = mapped_column(SmallInteger)
    birthday: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    platform_role: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=UserStatus.ACTIVE.value)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_users_tenant_phone",
            "tenant_id", "phone",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_users_tenant_email",
            "tenant_id", "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND email IS NOT NULL"),
        ),
        Index("idx_users_tenant_status", "tenant_id", "status"),
    )