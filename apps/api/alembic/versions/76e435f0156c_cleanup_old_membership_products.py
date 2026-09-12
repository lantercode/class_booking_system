"""cleanup_old_membership_products

删除 card_type 为空的旧会员卡产品数据。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76e435f0156c'
down_revision: Union[str, Sequence[str], None] = '57aeb9dcf020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 删除 card_type 为空或无效的旧产品数据
    op.execute(
        sa.text(
            "DELETE FROM membership_card_products "
            "WHERE card_type IS NULL OR card_type = ''"
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 无法恢复已删除的数据
    pass