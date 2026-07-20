from datetime import datetime

from app.shared.base_model import Base, TimestampMixin, TenantMixin
from sqlalchemy import BigInteger, String, SmallInteger, DateTime, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4
from enum import Enum


class BookingStatus(Enum):
    BOOKED = 1
    CANCELLED = 2
    CHECKED_IN = 3
    COMPLETED = 4
    NO_SHOW = 5


class BookingSource(Enum):
    SELF = "self"
    ADMIN = "admin"
    TEACHER = "teacher"


class Booking(Base, TenantMixin, TimestampMixin):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    schedule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("course_schedules.id", ondelete="RESTRICT"), nullable=False,
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BookingSource.SELF.value,
    )
    membership_card_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
    )
    booked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_reason: Mapped[str | None] = mapped_column(String(255))
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_bookings_schedule_student_active",
            "schedule_id", "student_id",
            unique=True,
            postgresql_where=text("status IN (1, 3, 4)"),
        ),
        Index("idx_bookings_student", "tenant_id", "student_id", "status"),
        Index("idx_bookings_schedule", "tenant_id", "schedule_id", "status"),
    )