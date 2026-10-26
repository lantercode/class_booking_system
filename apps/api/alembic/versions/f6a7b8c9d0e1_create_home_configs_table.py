"""create_home_configs_table

首页配置表：home_configs，按 scope(draft / published) + version 版本化存储，
draft 始终为 1 版本；published 每次发布递增 version。
查询"最新 published"靠 Service 层 max(version)。

create table + unique(tenant_id, scope, version) + idx(tenant_id, scope)
downgrade：drop_table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 home_configs 首页配置表。"""
    op.create_table(
        "home_configs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=20), nullable=False, comment="'draft' | 'published'"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1", comment="draft 始终 1；published 每次发布递增"),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="完整首页配置 JSON，顶层含 schema_version",
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True, comment="仅 published 记录有值"),
        sa.Column("operator_id", sa.BigInteger(), nullable=True, comment="操作人用户 ID"),
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
        sa.UniqueConstraint("tenant_id", "scope", "version", name="uq_home_configs_tenant_scope_version"),
    )
    op.create_index(
        "idx_home_configs_tenant_scope",
        "home_configs",
        ["tenant_id", "scope"],
    )


def downgrade() -> None:
    """删除 home_configs 表。"""
    op.drop_table("home_configs")
