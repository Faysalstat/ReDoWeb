"""paypal credit packs

Adds the admin-configurable `credit_packs` table and reshapes `purchases`
for PayPal (Stripe was never wired, so its unused session-id column is
renamed rather than kept alongside). Two placeholder packs are seeded
inactive -- an admin sets real names/prices and enables them.

Revision ID: b7d3f1a8c2e6
Revises: a1e5c9d34f7b
Create Date: 2026-10-05 00:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d3f1a8c2e6'
down_revision: Union[str, Sequence[str], None] = 'a1e5c9d34f7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    credit_packs = op.create_table(
        'credit_packs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('credits', sa.Integer(), nullable=False),
        sa.Column('price_usd_cents', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('updated_by_admin_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['updated_by_admin_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.bulk_insert(
        credit_packs,
        [
            {'id': uuid.uuid4(), 'name': 'Starter', 'credits': 10, 'price_usd_cents': 1000,
             'is_active': False, 'sort_order': 10},
            {'id': uuid.uuid4(), 'name': 'Value', 'credits': 50, 'price_usd_cents': 4500,
             'is_active': False, 'sort_order': 20},
        ],
    )

    op.alter_column('purchases', 'stripe_checkout_session_id', new_column_name='paypal_order_id')
    op.execute(
        'ALTER TABLE purchases RENAME CONSTRAINT purchases_stripe_checkout_session_id_key '
        'TO purchases_paypal_order_id_key'
    )
    op.add_column('purchases', sa.Column('paypal_capture_id', sa.String(length=255), nullable=True))
    op.create_unique_constraint('purchases_paypal_capture_id_key', 'purchases', ['paypal_capture_id'])
    op.add_column('purchases', sa.Column('credit_pack_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_purchases_credit_pack_id', 'purchases', 'credit_packs', ['credit_pack_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_purchases_credit_pack_id', 'purchases', type_='foreignkey')
    op.drop_column('purchases', 'credit_pack_id')
    op.drop_constraint('purchases_paypal_capture_id_key', 'purchases', type_='unique')
    op.drop_column('purchases', 'paypal_capture_id')
    op.execute(
        'ALTER TABLE purchases RENAME CONSTRAINT purchases_paypal_order_id_key '
        'TO purchases_stripe_checkout_session_id_key'
    )
    op.alter_column('purchases', 'paypal_order_id', new_column_name='stripe_checkout_session_id')
    op.drop_table('credit_packs')
