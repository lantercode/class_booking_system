"""add user_code to users

Revision ID: add_user_code_to_users
Revises: 107a2d677c16
Create Date: 2026-09-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_code_to_users'
down_revision: Union[str, None] = '107a2d677c16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('user_code', sa.String(20), nullable=True))
    op.create_index('ix_users_user_code', 'users', ['user_code'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_user_code', 'users')
    op.drop_column('users', 'user_code')