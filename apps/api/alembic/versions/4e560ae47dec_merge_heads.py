"""merge_heads

Revision ID: 4e560ae47dec
Revises: a1144bf59328, f1e2d3c4b5a6
Create Date: 2026-09-15 17:01:15.974159

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "4e560ae47dec"
down_revision: str | Sequence[str] | None = ("a1144bf59328", "f1e2d3c4b5a6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
