from app.shared.base_model import Base, TimestampMixin
from sqlalchemy import BigInteger, String, SmallInteger, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from uuid import uuid4
from enum import Enum


class TenantStatus(Enum):
    DISABLED = 0
    ACTIVE = 1


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    contact_email: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=TenantStatus.ACTIVE.value)
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_tenants_status", "status"),
    )