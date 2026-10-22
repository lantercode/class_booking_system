from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TenantMixin, TimestampMixin


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
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid4,
    )
    schedule_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("course_schedules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BookingSource.SELF.value,
    )
    membership_card_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("membership_cards.id", ondelete="SET NULL"),
        nullable=True,
    )
    booked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_reason: Mapped[str | None] = mapped_column(String(255))
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN (1, 2, 3, 4, 5)",
            name="ck_bookings_status",
        ),
        Index(
            "uq_bookings_schedule_student_active",
            "schedule_id",
            "student_id",
            unique=True,
            postgresql_where=text("status IN (1, 3, 4)"),
        ),
        Index("idx_bookings_student", "tenant_id", "student_id", "status"),
        Index("idx_bookings_schedule", "tenant_id", "schedule_id", "status"),
    )


class BookingReschedule(Base, TenantMixin, TimestampMixin):
    """改期 / 改派审计与幂等记录（F6.5）。

    不建任何指向 bookings / course_schedules / membership_cards 的外键：
    排期硬删除会级联删除 booking（D-10），FK 会阻断删除或丢失审计；
    所有关联 id 均为裸 BIGINT 快照。
    """

    __tablename__ = "booking_reschedules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid4,
    )
    old_booking_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    new_booking_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    old_schedule_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    new_schedule_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    old_membership_card_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    new_membership_card_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    operation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    request_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('reschedule','card_swap')",
            name="ck_booking_reschedules_type",
        ),
        # 同一旧预约至多一条改期记录（部分唯一）；纯改派可多条，不受限。
        Index(
            "uq_booking_reschedules_old_reschedule",
            "tenant_id",
            "old_booking_id",
            unique=True,
            postgresql_where=text("operation_type = 'reschedule'"),
        ),
        # 幂等键在租户内唯一（部分唯一，允许为空）。
        Index(
            "uq_booking_reschedules_request_key",
            "tenant_id",
            "request_key",
            unique=True,
            postgresql_where=text("request_key IS NOT NULL"),
        ),
        Index("idx_booking_reschedules_tenant_created", "tenant_id", text("created_at DESC")),
        Index("idx_booking_reschedules_new_booking", "tenant_id", "new_booking_id"),
    )
