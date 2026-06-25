from datetime import datetime

from app.shared.base_model import Base, TimestampMixin, TenantMixin
from sqlalchemy import BigInteger, String, SmallInteger, Text, Numeric, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4
from enum import Enum


class ClassroomStatus(Enum):
    DISABLED = 0
    ACTIVE = 1


class Classroom(Base, TenantMixin, TimestampMixin):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    equipment: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=ClassroomStatus.ACTIVE.value,
    )

    __table_args__ = (
        Index("uq_classrooms_tenant_name", "tenant_id", "name", unique=True),
    )


class CourseStatus(Enum):
    OFFLINE = 0
    ONLINE = 1


class Course(Base, TenantMixin, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    level: Mapped[str | None] = mapped_column(String(20))
    cover_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_capacity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    required_credits: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=CourseStatus.ONLINE.value,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "idx_courses_tenant_status", "tenant_id", "status",
            postgresql_where=deleted_at.is_(None),
        ),
        Index("idx_courses_tenant_category", "tenant_id", "category"),
    )