"""credit wallet

Revision ID: 2e4df342d3a0
Revises: 3ba1d9c75bd3
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2e4df342d3a0'
down_revision: Union[str, Sequence[str], None] = '3ba1d9c75bd3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('credit_wallets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('balance', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('credit_transactions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('wallet_id', sa.UUID(), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=32), nullable=False),
    sa.Column('related_project_id', sa.UUID(), nullable=True),
    sa.Column('related_job_id', sa.UUID(), nullable=True),
    sa.Column('related_purchase_id', sa.UUID(), nullable=True),
    sa.Column('idempotency_key', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['wallet_id'], ['credit_wallets.id'], ),
    sa.ForeignKeyConstraint(['related_project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['related_job_id'], ['generation_jobs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('credit_transactions')
    op.drop_table('credit_wallets')
