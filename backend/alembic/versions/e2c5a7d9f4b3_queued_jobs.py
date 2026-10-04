"""queued jobs

Revision ID: e2c5a7d9f4b3
Revises: d81a4e6f9c02
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e2c5a7d9f4b3'
down_revision: Union[str, Sequence[str], None] = 'd81a4e6f9c02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('queued_jobs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('task_name', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_queued_jobs_status_created_at', 'queued_jobs', ['status', 'created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_queued_jobs_status_created_at', table_name='queued_jobs')
    op.drop_table('queued_jobs')
