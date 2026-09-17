"""add_status_to_student_profiles

Revision ID: 448a38329d65
Revises: add_code_to_profiles
Create Date: 2026-09-17 19:19:44.409867

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "448a38329d65"
down_revision: str | Sequence[str] | None = "add_code_to_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 添加 status 字段
    op.add_column(
        "student_profiles",
        sa.Column(
            "status",
            sa.SmallInteger(),
            nullable=False,
            server_default="1",
            comment="状态：0禁用/1启用",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("student_profiles", "status")
