"""add_course_categories_table

Revision ID: 107a2d677c16
Revises: 07e19ff7324b
Create Date: 2026-09-17 14:39:17.253268

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "107a2d677c16"
down_revision: str | Sequence[str] | None = "07e19ff7324b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 创建 course_categories 表
    op.create_table(
        "course_categories",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "public_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            unique=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.BigInteger, nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("icon_url", sa.String(500)),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.Index("uq_course_categories_tenant_code", "tenant_id", "code", unique=True),
        sa.Index("uq_course_categories_tenant_name", "tenant_id", "name", unique=True),
        sa.Index("idx_course_categories_tenant_status", "tenant_id", "status"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("course_categories")
