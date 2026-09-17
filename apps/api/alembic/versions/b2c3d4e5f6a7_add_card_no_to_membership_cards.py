"""add_card_no_to_membership_cards

为 membership_cards 表添加 card_no 字段（会员卡号）。
生成规则：yyyyMMdd + 9位随机数
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "f6e5d4c3b2a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "membership_cards",
        sa.Column(
            "card_no",
            sa.String(17),
            nullable=True,
            comment="会员卡号（yyyyMMdd + 9位随机数）",
        ),
    )
    op.create_index("idx_cards_card_no", "membership_cards", ["card_no"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_cards_card_no", "membership_cards")
    op.drop_column("membership_cards", "card_no")
