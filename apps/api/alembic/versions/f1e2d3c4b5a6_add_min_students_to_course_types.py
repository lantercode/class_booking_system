"""add_min_students_to_course_types

为 course_types 表添加 min_students 字段，用于设置常规课最低成课人数。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1e2d3c4b5a6"
down_revision: str | Sequence[str] | None = "e12d902b49f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "course_types",
        sa.Column(
            "min_students",
            sa.SmallInteger(),
            nullable=True,
            comment="最低成课人数（仅常规课有效，NULL表示不限制）",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("course_types", "min_students")
