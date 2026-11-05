"""add_membership_card_soft_delete

为 membership_cards 增加软删除字段：已作废的卡可以被"删除"（仅打标，不物理删除），
从而在后台列表中不再堆积，同时保留流水、审计与历史预约的溯源。

改动：
  1. 新增 deleted_at / deleted_by / deleted_reason 三列（均可空，对存量数据无影响）；
  2. 新增索引 idx_cards_deleted_at（tenant_id, deleted_at），支撑默认过滤。

Revision ID: c1d2e3f4a5b6
Revises: f6a7b8c9d0e1
Create Date: 2026-11-05

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "membership_cards"
INDEX_NAME = "idx_cards_deleted_at"


def upgrade() -> None:
    """Upgrade schema：新增软删除列与索引。"""
    op.add_column(
        TABLE_NAME,
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="软删除时间（仅已作废的卡允许删除）",
        ),
    )
    op.add_column(
        TABLE_NAME,
        sa.Column(
            "deleted_by",
            sa.BigInteger(),
            nullable=True,
            comment="删除操作人ID",
        ),
    )
    op.add_column(
        TABLE_NAME,
        sa.Column(
            "deleted_reason",
            sa.String(length=255),
            nullable=True,
            comment="删除原因",
        ),
    )
    op.create_index(
        index_name=INDEX_NAME,
        table_name=TABLE_NAME,
        columns=["tenant_id", "deleted_at"],
    )


def downgrade() -> None:
    """Downgrade schema：先删索引，再删列。"""
    op.drop_index(index_name=INDEX_NAME, table_name=TABLE_NAME)
    op.drop_column(TABLE_NAME, "deleted_reason")
    op.drop_column(TABLE_NAME, "deleted_by")
    op.drop_column(TABLE_NAME, "deleted_at")
