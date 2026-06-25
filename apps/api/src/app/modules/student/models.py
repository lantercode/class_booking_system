from app.shared.base_model import Base, TenantMixin, TimestampMixin
from sqlalchemy import BigInteger, String, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column


class StudentProfile(Base, TenantMixin, TimestampMixin):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(String(50))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20))
    level: Mapped[str | None] = mapped_column(String(20))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_student_profiles_tenant", "tenant_id"),
    )