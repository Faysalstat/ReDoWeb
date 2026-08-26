"""purchases

Revision ID: a4f2b8c1d3e5
Revises: 7f3a1c9e4b21
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a4f2b8c1d3e5'
down_revision: Union[str, Sequence[str], None] = '7f3a1c9e4b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('purchases',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('amount_usd_cents', sa.Integer(), nullable=False),
    sa.Column('credits_granted', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('stripe_checkout_session_id', sa.String(length=255), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_by_admin_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('stripe_checkout_session_id')
    )
    # related_purchase_id predates this table (was a plain UUID column with
    # no FK) -- safe to constrain now since no purchases existed before this.
    op.create_foreign_key(
        'fk_credit_transactions_related_purchase_id',
        'credit_transactions', 'purchases',
        ['related_purchase_id'], ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_credit_transactions_related_purchase_id', 'credit_transactions', type_='foreignkey')
    op.drop_table('purchases')
