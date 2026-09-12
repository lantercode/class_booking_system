"""add_membership_card_constraints

添加数据库约束防止数据不一致：
- 添加 CHECK 约束防止 used_credits > total_credits
- 添加 CHECK 约束防止 balance_after < 0
- 添加唯一约束防止重复发卡（可选）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 添加 CHECK 约束：已使用次数不能超过总次数
    op.execute("""
        ALTER TABLE membership_cards
        ADD CONSTRAINT chk_used_credits_valid
        CHECK (
            total_credits IS NULL
            OR used_credits <= total_credits
        )
    """)
    
    # 添加 CHECK 约束：余额不能为负数
    op.execute("""
        ALTER TABLE membership_card_transactions
        ADD CONSTRAINT chk_balance_after_non_negative
        CHECK (balance_after >= 0)
    """)
    
    # 添加 CHECK 约束：总次数必须为正数（如果设置了）
    op.execute("""
        ALTER TABLE membership_cards
        ADD CONSTRAINT chk_total_credits_positive
        CHECK (total_credits IS NULL OR total_credits > 0)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        ALTER TABLE membership_cards
        DROP CONSTRAINT IF EXISTS chk_used_credits_valid
    """)
    
    op.execute("""
        ALTER TABLE membership_card_transactions
        DROP CONSTRAINT IF EXISTS chk_balance_after_non_negative
    """)
    
    op.execute("""
        ALTER TABLE membership_cards
        DROP CONSTRAINT IF EXISTS chk_total_credits_positive
    """)
