"""create_notifications_table

站内消息表：notifications。
- 幂等：unique(tenant_id, idempotency_key)，重复投递不产生第二条消息；
- 查询：idx(tenant_id, user_id, created_at DESC)。

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-11-23

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="接收人用户ID"),
        sa.Column("type", sa.String(length=30), nullable=False, comment="消息类型"),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
            name="uq_notifications_tenant_idempotency",
        ),
    )
    op.create_index(
        "idx_notifications_user_created",
        "notifications",
        ["tenant_id", "user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("notifications")
