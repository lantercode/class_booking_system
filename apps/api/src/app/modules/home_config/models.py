"""
Home Config Models - 首页配置模型

home_configs 表按 scope(draft / published) + version 版本化存储：
- draft 始终 version=1（单租户一条）
- published 每次发布 version 递增（历史版本快照）
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TenantMixin, TimestampMixin


class HomeConfig(Base, TenantMixin, TimestampMixin):
    """首页配置版本化记录"""

    __tablename__ = "home_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="'draft' | 'published'"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="draft 始终 1；published 每次发布递增"
    )
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="完整首页配置 JSON，顶层含 schema_version"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="仅 published 记录有值"
    )
    operator_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作人用户 ID",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scope", "version", name="uq_home_configs_tenant_scope_version"
        ),
    )
