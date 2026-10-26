"""
Upload Module Models - 文件上传模块数据模型

FileObject：上传审计表，记录每次上传的文件元数据。
业务表（users.avatar_url / classrooms.cover_image_url 等）只存 object_key，
完整 URL 由 Service 层拼装。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TenantMixin


class FileObject(Base, TenantMixin):
    """
    文件对象审计表。

    记录每次上传的文件元数据，支撑 avatar / classroom_cover / banner /
    video_cover / notice 等业务场景。业务表只引用 object_key。
    """

    __tablename__ = "file_objects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    object_key: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="存储对象 key（如 t/1/avatar/uuid.jpg）"
    )
    mime: Mapped[str] = mapped_column(String(50), nullable=False, comment="MIME 类型")
    size: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="文件字节数")
    biz_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="业务场景：avatar | classroom_cover | banner | video_cover | notice",
    )
    uploader_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "object_key", name="uq_file_objects_tenant_key"),
    )
