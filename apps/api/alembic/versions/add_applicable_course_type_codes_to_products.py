"""add applicable_course_type_codes to membership products and cards

Revision ID: add_applicable_course_type_codes
Revises: add_course_types
Create Date: 2026-09-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_applicable_course_type_codes'
down_revision: Union[str, None] = 'add_course_types'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为 membership_card_products 表添加 applicable_course_type_codes 字段
    op.add_column(
        'membership_card_products',
        sa.Column(
            'applicable_course_type_codes',
            sa.dialects.postgresql.ARRAY(sa.String(50)),
            nullable=True,
            comment='适用的课程类型代码列表，NULL表示不限'
        )
    )

    # 为 membership_cards 表添加 applicable_course_type_codes 字段
    op.add_column(
        'membership_cards',
        sa.Column(
            'applicable_course_type_codes',
            sa.dialects.postgresql.ARRAY(sa.String(50)),
            nullable=True,
            comment='适用的课程类型代码列表（从产品继承）'
        )
    )


def downgrade() -> None:
    op.drop_column('membership_cards', 'applicable_course_type_codes')
    op.drop_column('membership_card_products', 'applicable_course_type_codes')