"""add_product_deleted_at

为 membership_card_products 表添加 deleted_at 字段，用于区分下架和删除。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e12d902b49f2'
down_revision: Union[str, Sequence[str], None] = '76e435f0156c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'membership_card_products',
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='删除时间（软删除）')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('membership_card_products', 'deleted_at')