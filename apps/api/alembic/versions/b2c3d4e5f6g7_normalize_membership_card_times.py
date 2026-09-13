"""normalize_membership_card_times

将 membership_cards 表中已有数据的时间规范化：
- valid_from 的时分秒统一为 00:00:00
- expire_at 的时分秒统一为 23:59:59
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 更新 valid_from 的时分秒为 00:00:00
    op.execute("""
        UPDATE membership_cards
        SET valid_from = DATE_TRUNC('day', valid_from)
        WHERE valid_from IS NOT NULL
          AND EXTRACT(HOUR FROM valid_from) != 0
    """)

    # 更新 expire_at 的时分秒为 23:59:59
    op.execute("""
        UPDATE membership_cards
        SET expire_at = DATE_TRUNC('day', expire_at) + INTERVAL '23:59:59'
        WHERE expire_at IS NOT NULL
          AND (EXTRACT(HOUR FROM expire_at) != 23
               OR EXTRACT(MINUTE FROM expire_at) != 59
               OR EXTRACT(SECOND FROM expire_at) != 59)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # downgrade 操作无法恢复原始时间，所以不做任何操作
    pass
