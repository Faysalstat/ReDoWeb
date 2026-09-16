"""db-backed ai model selection

Revision ID: 7ba9d237ac0b
Revises: e2c5a7d9f4b3
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7ba9d237ac0b'
down_revision: Union[str, Sequence[str], None] = 'e2c5a7d9f4b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tiers', sa.Column('generation_model', sa.String(length=128), nullable=True))

    op.create_table('ai_model_settings',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('model_name', sa.String(length=128), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by_admin_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['updated_by_admin_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ai_model_settings')
    op.drop_column('tiers', 'generation_model')
