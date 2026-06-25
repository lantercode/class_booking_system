from datetime import datetime

from app.shared.base_model import Base, TimestampMixin, TenantMixin
from sqlalchemy import BigInteger, String, SmallInteger, Integer, Numeric, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4
from enum import Enum


class CardType(Enum):
    COUNT = "count"
    PERIOD = "period"
    UNLIMITED = "unlimited"


class MembershipCardStatus(Enum):
    DISABLED = 0
    ACTIVE = 1


class MembershipCard(Base, TenantMixin, TimestampMixin):
    __tablename__ = "membership_cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    card_type: Mapped[str] = mapped_column(String(20), nullable=False)
    total_credits: Mapped[int | None] = mapped_column(Integer)
    used_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=MembershipCardStatus.ACTIVE.value,
    )

    __table_args__ = (
        Index("idx_cards_student", "tenant_id", "student_id", "status"),
    )


class ItemType(Enum):
    CARD = "card"
    COURSE = "course"


class OrderStatus(Enum):
    PENDING = 0
    PAID = 1
    CANCELLED = 2
    REFUNDED = 3


class Order(Base, TenantMixin, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    order_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=OrderStatus.PENDING.value)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_orders_user", "tenant_id", "user_id", "status"),
        Index("idx_orders_status_created", "tenant_id", "status", text("created_at DESC")),
    )