"""tiers

Revision ID: b58e1a92c7f0
Revises: a4f2b8c1d3e5
Create Date: 2026-08-12 00:00:01.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b58e1a92c7f0'
down_revision: Union[str, Sequence[str], None] = 'a4f2b8c1d3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


tiers_table = sa.table(
    'tiers',
    sa.column('id', sa.UUID()),
    sa.column('key', sa.String),
    sa.column('label', sa.String),
    sa.column('is_active', sa.Boolean),
    sa.column('sort_order', sa.Integer),
    sa.column('download_credit_cost', sa.Integer),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('tiers',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=32), nullable=False),
    sa.Column('label', sa.String(length=64), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('download_credit_cost', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key')
    )
    # Backfill: exactly the 3 rows previously hardcoded in tier_service.py's
    # _TIERS list, so behavior is unchanged the moment the service switches
    # to reading from this table.
    op.bulk_insert(tiers_table, [
        {'id': uuid.uuid4(), 'key': 'basic', 'label': 'Basic', 'is_active': False, 'sort_order': 1, 'download_credit_cost': 3},
        {'id': uuid.uuid4(), 'key': 'premium', 'label': 'Premium', 'is_active': False, 'sort_order': 2, 'download_credit_cost': 5},
        {'id': uuid.uuid4(), 'key': 'pro', 'label': 'Pro', 'is_active': True, 'sort_order': 3, 'download_credit_cost': 10},
    ])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('tiers')
