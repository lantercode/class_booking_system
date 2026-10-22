"""add_frozen_remaining_days_to_membership_cards

为 membership_cards 表添加 frozen_remaining_days 字段，
用于在解冻时精确计算有效期。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "835a06fcf236"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "membership_cards",
        sa.Column(
            "frozen_remaining_days",
            sa.Integer(),
            nullable=True,
            comment="冻结时剩余的有效天数（用于解冻时重新计算有效期）",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("membership_cards", "frozen_remaining_days")