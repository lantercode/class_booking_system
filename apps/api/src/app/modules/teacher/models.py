from app.shared.base_model import Base, TimestampMixin, TenantMixin
from sqlalchemy import BigInteger, String, SmallInteger, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum


class TeacherStatus(Enum):
    DISABLED = 0
    ACTIVE = 1


class TeacherProfile(Base, TenantMixin, TimestampMixin):
    __tablename__ = "teacher_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    title: Mapped[str | None] = mapped_column(String(100))
    bio: Mapped[str | None] = mapped_column(Text)
    specialties: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    years_of_experience: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=TeacherStatus.ACTIVE.value,
    )

    __table_args__ = (
        Index("idx_teacher_profiles_tenant", "tenant_id", "status"),
    )