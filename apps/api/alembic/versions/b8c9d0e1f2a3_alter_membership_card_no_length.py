"""alter_membership_card_no_length

会员卡卡号生成规则由 yyyyMMdd+9位随机数 调整为 MC+yyyyMMdd+9位随机数，
长度由 17 字符增至 19 字符，需同步放宽 membership_cards.card_no 列长度。

upgrade：ALTER COLUMN card_no TYPE VARCHAR(19)
downgrade：ALTER COLUMN card_no TYPE VARCHAR(17)

Revision ID: b8c9d0e1f2a3
Revises: f6a5b4c3d2e1
Create Date: 2026-10-24

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "f6a5b4c3d2e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """放宽 card_no 列长度至 19 字符（MC + yyyyMMdd + 9位随机数）。"""
    op.alter_column(
        "membership_cards",
        "card_no",
        existing_type=sa.String(length=17),
        type_=sa.String(length=19),
        existing_comment="会员卡号（yyyyMMdd + 9位随机数）",
        comment="会员卡号（MC + yyyyMMdd + 9位随机数）",
    )


def downgrade() -> None:
    """回退 card_no 列长度至 17 字符。"""
    op.alter_column(
        "membership_cards",
        "card_no",
        existing_type=sa.String(length=19),
        type_=sa.String(length=17),
        existing_comment="会员卡号（MC + yyyyMMdd + 9位随机数）",
        comment="会员卡号（yyyyMMdd + 9位随机数）",
    )
