from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, Index, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TenantMixin, TimestampMixin


class ClassroomStatus(Enum):
    DISABLED = 0
    ACTIVE = 1


class Classroom(Base, TenantMixin, TimestampMixin):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
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


class CourseTypeStatus(Enum):
    DISABLED = 0
    ACTIVE = 1


class CourseType(Base, TenantMixin, TimestampMixin):
    """课程类型（按授课形式分类：常规课、特色课、私教课等）"""
    __tablename__ = "course_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="类型名称")
    code: Mapped[str] = mapped_column(String(50), nullable=False, comment="类型代码")
    description: Mapped[str | None] = mapped_column(Text, comment="描述")
    required_card_types: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)), nullable=True, comment="需要的会员卡类型列表",
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=CourseTypeStatus.ACTIVE.value, comment="状态",
    )

    __table_args__ = (
        Index("uq_course_types_tenant_code", "tenant_id", "code", unique=True),
        Index("uq_course_types_tenant_name", "tenant_id", "name", unique=True),
        Index("idx_course_types_tenant_status", "tenant_id", "status"),
    )


class Course(Base, TenantMixin, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    course_type_code: Mapped[str | None] = mapped_column(String(50), comment="课程类型代码")
    level: Mapped[str | None] = mapped_column(String(20))
    cover_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
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
        Index("idx_courses_tenant_type", "tenant_id", "course_type_code"),
    )