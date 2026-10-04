"""model pricing

Revision ID: c69f2b03d8a1
Revises: b58e1a92c7f0
Create Date: 2026-08-12 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c69f2b03d8a1'
down_revision: Union[str, Sequence[str], None] = 'b58e1a92c7f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


model_pricing_table = sa.table(
    'model_pricing',
    sa.column('model_name', sa.String),
    sa.column('prompt_price_per_1m', sa.Numeric),
    sa.column('completion_price_per_1m', sa.Numeric),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('model_pricing',
    sa.Column('model_name', sa.String(length=128), nullable=False),
    sa.Column('prompt_price_per_1m', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('completion_price_per_1m', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by_admin_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['updated_by_admin_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('model_name')
    )
    # Backfill: the 2 models previously hardcoded in
    # token_usage_service.MODEL_PRICING_PER_1M, plus the actually-configured
    # generation model (anthropic/claude-opus-5), which that dict was
    # silently missing -- every real generation call was pricing at $0.00
    # before this. Source: openrouter.ai/anthropic/claude-opus-5 (verified
    # 2026-08-12): $5/1M prompt, $25/1M completion.
    op.bulk_insert(model_pricing_table, [
        {'model_name': 'openai/gpt-4o-mini', 'prompt_price_per_1m': 0.15, 'completion_price_per_1m': 0.60},
        {'model_name': 'anthropic/claude-sonnet-4.5', 'prompt_price_per_1m': 3.00, 'completion_price_per_1m': 15.00},
        {'model_name': 'anthropic/claude-opus-5', 'prompt_price_per_1m': 5.00, 'completion_price_per_1m': 25.00},
    ])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('model_pricing')
