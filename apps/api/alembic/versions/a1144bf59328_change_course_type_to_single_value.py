"""change course type to single value

Revision ID: a1144bf59328
Revises: c17b284c3335
Create Date: 2026-09-14 16:50:00.616022

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1144bf59328"
down_revision: str | Sequence[str] | None = "c17b284c3335"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 为 membership_card_products 表添加新的单值字段
    op.add_column(
        "membership_card_products",
        sa.Column(
            "applicable_course_type_code",
            sa.String(50),
            nullable=True,
            comment="适用的课程类型代码（单选），NULL表示不限",
        ),
    )

    # 2. 从数组字段中迁移数据到新字段（取数组第一个值）
    op.execute("""
        UPDATE membership_card_products
        SET applicable_course_type_code = applicable_course_type_codes[1]
        WHERE applicable_course_type_codes IS NOT NULL
          AND array_length(applicable_course_type_codes, 1) > 0
    """)

    # 3. 删除旧的数组字段
    op.drop_column("membership_card_products", "applicable_course_type_codes")

    # 4. 对 membership_cards 表做同样处理
    op.add_column(
        "membership_cards",
        sa.Column(
            "applicable_course_type_code",
            sa.String(50),
            nullable=True,
            comment="适用的课程类型代码（从产品继承，单选）",
        ),
    )

    op.execute("""
        UPDATE membership_cards
        SET applicable_course_type_code = applicable_course_type_codes[1]
        WHERE applicable_course_type_codes IS NOT NULL
          AND array_length(applicable_course_type_codes, 1) > 0
    """)

    op.drop_column("membership_cards", "applicable_course_type_codes")


def downgrade() -> None:
    """Downgrade schema."""
    # 1. 恢复 membership_cards 表的数组字段
    op.add_column(
        "membership_cards",
        sa.Column(
            "applicable_course_type_codes",
            sa.ARRAY(sa.String(50)),
            nullable=True,
            comment="适用的课程类型代码列表（从产品继承）",
        ),
    )

    op.execute("""
        UPDATE membership_cards
        SET applicable_course_type_codes = ARRAY[applicable_course_type_code]
        WHERE applicable_course_type_code IS NOT NULL
    """)

    op.drop_column("membership_cards", "applicable_course_type_code")

    # 2. 恢复 membership_card_products 表的数组字段
    op.add_column(
        "membership_card_products",
        sa.Column(
            "applicable_course_type_codes",
            sa.ARRAY(sa.String(50)),
            nullable=True,
            comment="适用的课程类型代码列表，NULL表示不限",
        ),
    )

    op.execute("""
        UPDATE membership_card_products
        SET applicable_course_type_codes = ARRAY[applicable_course_type_code]
        WHERE applicable_course_type_code IS NOT NULL
    """)

    op.drop_column("membership_card_products", "applicable_course_type_code")
