"""create_job_queue_table

任务队列表：job_queue。
- 幂等：unique(tenant_id, idempotency_key)，重复投递不产生第二条
- 多 worker 抢锁：`FOR UPDATE SKIP LOCKED` 天然互斥
- 租约：locked_by + locked_at，超时后自动回收
- 退避重试：status=failed + attempts 上限 → dead
- 只承载副作用（通知、扣次、退款、状态回写），状态正确性由 P3-0 纯派生保证

Revision ID: f7a8b9c0d1e2
Revises: e2f3a4b5c6d7
Create Date: 2026-11-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_queue",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=50), nullable=False, comment="任务类型枚举"),
        sa.Column(
            "idempotency_key",
            sa.String(length=120),
            nullable=False,
            comment="同租户内唯一，防重复执行",
        ),
        sa.Column(
            "payload",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="任务参数 JSON",
        ),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="计划执行时间（UTC）",
        ),
        sa.Column(
            "status",
            sa.String(length=12),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="pending/running/done/failed/dead",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
            comment="最近一次失败的 traceback / 业务错误",
        ),
        sa.Column(
            "locked_by",
            sa.String(length=32),
            nullable=True,
            comment="worker 租约持有者（机器+进程标识）",
        ),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="租约开始时间，超时可被其他 worker 回收",
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="完成（done / dead）时间",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_job_queue_tenant_idempotency",
        ),
    )
    op.create_index(
        "idx_job_queue_status_runat",
        "job_queue",
        ["status", "run_at"],
    )
    op.create_index(
        "idx_job_queue_tenant_status",
        "job_queue",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("job_queue")
