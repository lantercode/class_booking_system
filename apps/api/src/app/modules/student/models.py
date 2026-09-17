from enum import Enum

from sqlalchemy import BigInteger, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TenantMixin, TimestampMixin


class StudentStatus(Enum):
    """学员状态"""
    DISABLED = 0
    ACTIVE = 1


class StudentProfile(Base, TenantMixin, TimestampMixin):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    student_code: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True, comment="学员编号：S + yyyyMMdd + 6位随机数"
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(String(50))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20))
    level: Mapped[str | None] = mapped_column(String(20))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=StudentStatus.ACTIVE.value,
    )

    __table_args__ = (Index("idx_student_profiles_tenant", "tenant_id"),)