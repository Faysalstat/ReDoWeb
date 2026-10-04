"""add tiers updated_by_admin_id

Revision ID: e14eca398b7e
Revises: 5f88f9acc922
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e14eca398b7e'
down_revision: Union[str, Sequence[str], None] = '5f88f9acc922'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tiers', sa.Column('updated_by_admin_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_tiers_updated_by_admin_id', 'tiers', 'users', ['updated_by_admin_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_tiers_updated_by_admin_id', 'tiers', type_='foreignkey')
    op.drop_column('tiers', 'updated_by_admin_id')
