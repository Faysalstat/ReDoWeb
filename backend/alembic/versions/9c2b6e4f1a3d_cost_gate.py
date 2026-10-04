"""cost gate

Revision ID: 9c2b6e4f1a3d
Revises: 5d005e06ba56
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9c2b6e4f1a3d'
down_revision: Union[str, Sequence[str], None] = '5d005e06ba56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'cost_settings',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by_admin_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by_admin_id'], ['users.id']),
        sa.PrimaryKeyConstraint('key'),
    )
    op.add_column('projects', sa.Column('estimated_generation_cost_usd', sa.Float(), nullable=True))
    op.add_column('projects', sa.Column('pending_tier_keys', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'pending_tier_keys')
    op.drop_column('projects', 'estimated_generation_cost_usd')
    op.drop_table('cost_settings')
