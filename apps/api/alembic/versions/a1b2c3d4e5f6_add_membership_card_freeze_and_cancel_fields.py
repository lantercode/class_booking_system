"""add_membership_card_freeze_and_cancel_fields

为 membership_cards 表添加冻结和作废相关字段：
- frozen_until: 冻结到期时间（NULL表示无限期冻结）
- cancelled_at: 作废时间
- cancelled_reason: 作废原因
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e12d902b49f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 添加 frozen_until 字段
    op.add_column(
        'membership_cards',
        sa.Column('frozen_until', sa.TIMESTAMP(timezone=True), nullable=True, comment='冻结到期时间（NULL表示无限期冻结）')
    )
    
    # 添加 cancelled_at 字段
    op.add_column(
        'membership_cards',
        sa.Column('cancelled_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='作废时间')
    )
    
    # 添加 cancelled_reason 字段
    op.add_column(
        'membership_cards',
        sa.Column('cancelled_reason', sa.String(255), nullable=True, comment='作废原因')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('membership_cards', 'cancelled_reason')
    op.drop_column('membership_cards', 'cancelled_at')
    op.drop_column('membership_cards', 'frozen_until')