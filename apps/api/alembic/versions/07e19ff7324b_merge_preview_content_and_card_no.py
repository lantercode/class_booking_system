"""merge_preview_content_and_card_no

Revision ID: 07e19ff7324b
Revises: add_schedule_preview_content, b2c3d4e5f6a7
Create Date: 2026-09-17 14:17:25.809225

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "07e19ff7324b"
down_revision: str | Sequence[str] | None = ("add_schedule_preview_content", "b2c3d4e5f6a7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
