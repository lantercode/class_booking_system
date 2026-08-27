from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TenantMixin, TimestampMixin


class PaymentChannel(Enum):
    WECHAT = "wechat"
    ALIPAY = "alipay"


class PaymentStatus(Enum):
    PENDING = 0
    PAID = 1


class Payment(Base, TenantMixin, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    out_trade_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    transaction_id: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=PaymentStatus.PENDING.value,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_response: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("idx_payments_order", "order_id"),
    )
