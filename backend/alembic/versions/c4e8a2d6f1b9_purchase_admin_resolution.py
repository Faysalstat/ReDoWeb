"""purchase admin resolution + refunded_at

Revision ID: c4e8a2d6f1b9
Revises: b7d3f1a8c2e6
Create Date: 2026-10-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a2d6f1b9'
down_revision: Union[str, Sequence[str], None] = 'b7d3f1a8c2e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('purchases', sa.Column('resolved_by_admin_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_purchases_resolved_by_admin_id', 'purchases', 'users', ['resolved_by_admin_id'], ['id']
    )
    op.add_column('purchases', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('purchases', sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('purchases', 'refunded_at')
    op.drop_column('purchases', 'resolved_at')
    op.drop_constraint('fk_purchases_resolved_by_admin_id', 'purchases', type_='foreignkey')
    op.drop_column('purchases', 'resolved_by_admin_id')
