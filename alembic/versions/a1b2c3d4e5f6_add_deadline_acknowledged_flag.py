"""add deadline acknowledged flag

Revision ID: a1b2c3d4e5f6
Revises: 7d67e0a7c770
Create Date: 2026-09-09 17:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7d67e0a7c770'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('deadline_acknowledged', sa.Boolean(), nullable=True, server_default=sa.text('false')))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tasks', 'deadline_acknowledged')
