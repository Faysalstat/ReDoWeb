"""project soft delete (admin)

Revision ID: c8e3a1f5d9b2
Revises: b2d6f8a4c1e7
Create Date: 2026-10-06 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c8e3a1f5d9b2'
down_revision: Union[str, Sequence[str], None] = 'b2d6f8a4c1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projects', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'projects',
        sa.Column('deleted_by_admin_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )
    op.add_column('projects', sa.Column('deletion_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'deletion_reason')
    op.drop_column('projects', 'deleted_by_admin_id')
    op.drop_column('projects', 'deleted_at')
