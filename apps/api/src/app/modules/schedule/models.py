from datetime import datetime

from app.shared.base_model import Base, TimestampMixin, TenantMixin
from sqlalchemy import BigInteger, SmallInteger, Text, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4
from enum import Enum


class ScheduleStatus(Enum):
    CANCELLED = 2
    NORMAL = 1
    FINISHED = 3


class CourseSchedule(Base, TenantMixin, TimestampMixin):
    __tablename__ = "course_schedules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False,
    )
    teacher_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    classroom_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("classrooms.id", ondelete="SET NULL"),
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    booked_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    booking_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    booking_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=ScheduleStatus.NORMAL.value,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("end_at > start_at", name="chk_schedule_time"),
        CheckConstraint(
            "booked_count <= capacity AND booked_count >= 0",
            name="chk_schedule_capacity",
        ),
        Index("idx_schedules_tenant_start", "tenant_id", "start_at"),
        Index("idx_schedules_teacher_start", "tenant_id", "teacher_id", "start_at"),
        Index("idx_schedules_classroom_start", "tenant_id", "classroom_id", "start_at"),
        Index("idx_schedules_course", "course_id"),
    )