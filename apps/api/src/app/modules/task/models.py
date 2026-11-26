"""job_queue ORM 模型。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TenantMixin, TimestampMixin


class JobStatus:
    """任务状态枚举（字符串常量，无额外 Enum 类，查询时易用）。"""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    DEAD = "dead"


JOB_STATUS_VALUES = frozenset({JobStatus.PENDING, JobStatus.RUNNING, JobStatus.DONE, JobStatus.FAILED, JobStatus.DEAD})


class JobQueue(Base, TenantMixin, TimestampMixin):
    """延迟任务队列表。

    用途：承载需副作用（通知、扣次、退款、状态回写）但不承担状态正确性的任务。
    状态正确性由 P3-0 纯派生保证；队列只保证"该发生的副作用不丢、可重试、可审计"。
    """

    __tablename__ = "job_queue"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, comment="任务类型枚举")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB(astext_type=Text()), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=func.text("'pending'")
    )
    attempts: Mapped[int] = mapped_column(nullable=False, server_default=func.text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_job_queue_tenant_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
        ),
        Index("idx_job_queue_status_runat", "status", "run_at"),
        Index("idx_job_queue_tenant_status", "tenant_id", "status"),
    )
