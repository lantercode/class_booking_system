"""add_cancel_before_minutes_to_course_types

为 course_types 表添加 cancel_before_minutes 字段，用于设置开课前多少分钟不能取消课程。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6e5d4c3b2a1"
down_revision: str | Sequence[str] | None = "4e560ae47dec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "course_types",
        sa.Column(
            "cancel_before_minutes",
            sa.SmallInteger(),
            nullable=True,
            comment="开课前多少分钟不能取消（仅常规课有效，NULL表示不限制）",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("course_types", "cancel_before_minutes")
