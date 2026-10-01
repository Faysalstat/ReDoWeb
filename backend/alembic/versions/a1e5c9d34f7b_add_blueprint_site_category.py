"""add blueprint site_category

Revision ID: a1e5c9d34f7b
Revises: 9c2b6e4f1a3d
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1e5c9d34f7b'
down_revision: Union[str, Sequence[str], None] = '9c2b6e4f1a3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('blueprints', sa.Column('site_category', sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('blueprints', 'site_category')
