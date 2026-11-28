"""create_idempotency_keys_table

写操作幂等键表：idempotency_keys。
- unique(tenant_id, scope, key)：并发同 key 重试只保留一条记录
- request_hash：同 key 但请求参数不同时返回 409
- booking_id：指向首次创建的预约（SET NULL，排期级联删除预约时不阻断）
- (tenant_id, created_at)：便于后续按租户 + 时间清理过期记录

Revision ID: c9d0e1f2a3b4
Revises: f7a8b9c0d1e2
Create Date: 2026-11-28

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope",
            sa.String(length=32),
            nullable=False,
            comment="幂等域，如 booking.create",
        ),
        sa.Column("key", sa.String(length=64), nullable=False, comment="客户端幂等键"),
        sa.Column(
            "request_hash",
            sa.String(length=64),
            nullable=False,
            comment="请求参数指纹（sha256 hex）",
        ),
        sa.Column(
            "booking_id",
            sa.BigInteger(),
            sa.ForeignKey("bookings.id", ondelete="SET NULL"),
            nullable=True,
            comment="首次创建预约ID",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_idempotency_keys_tenant_id",
        "idempotency_keys",
        ["tenant_id"],
    )
    op.create_index(
        "uq_idempotency_keys_tenant_scope_key",
        "idempotency_keys",
        ["tenant_id", "scope", "key"],
        unique=True,
    )
    op.create_index(
        "idx_idempotency_keys_tenant_created",
        "idempotency_keys",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_idempotency_keys_tenant_created", table_name="idempotency_keys")
    op.drop_index("uq_idempotency_keys_tenant_scope_key", table_name="idempotency_keys")
    op.drop_index("ix_idempotency_keys_tenant_id", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
