"""merge_heads_for_frozen_remaining_days

Revision ID: 211f847af16c
Revises: 835a06fcf236, ef07aa8bcff8
Create Date: 2026-09-20 14:24:27.277249

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '211f847af16c'
down_revision: str | Sequence[str] | None = ('835a06fcf236', 'ef07aa8bcff8')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
