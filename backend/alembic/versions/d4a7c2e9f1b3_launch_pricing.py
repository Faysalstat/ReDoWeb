"""launch pricing: tier download costs + matching credit packs

Data-only (user decision 2026-10-10): 1 credit ~= $1, tier download costs
Basic 20 / Premium 50 / Pro 60 credits (Pro is the top tier), and one active credit pack per tier
price (20 credits $20, 50 credits $50, 60 credits $60) so a single pack
always covers one download. Tier on/off state is not touched (Basic stays
disabled). The placeholder packs seeded inactive by b7d3f1a8c2e6 are left as
they are -- packs are never deleted, so purchase history stays meaningful.

Everything here stays admin-editable afterwards (Tiers & pricing page); this
only gives every environment (local, Railway) the same starting point.

Revision ID: d4a7c2e9f1b3
Revises: c8e3a1f5d9b2
Create Date: 2026-10-10 10:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a7c2e9f1b3'
down_revision: Union[str, Sequence[str], None] = 'c8e3a1f5d9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIER_COSTS = {'basic': 20, 'premium': 50, 'pro': 60}
# Pre-launch seed values from b58e1a92c7f0, restored on downgrade.
PREVIOUS_TIER_COSTS = {'basic': 3, 'premium': 5, 'pro': 10}

PACKS = [
    # (name, credits, price_usd_cents, sort_order)
    ('Basic pack', 20, 2000, 100),
    ('Premium pack', 50, 5000, 110),
    ('Pro pack', 60, 6000, 120),
]


def _set_tier_costs(costs: dict[str, int]) -> None:
    for key, cost in costs.items():
        op.execute(
            sa.text('UPDATE tiers SET download_credit_cost = :cost WHERE key = :key').bindparams(
                cost=cost, key=key
            )
        )


def upgrade() -> None:
    _set_tier_costs(TIER_COSTS)
    for name, credits, cents, sort_order in PACKS:
        # Idempotent: skip if an identical pack already exists (e.g. an admin
        # created it by hand before this migration ran).
        op.execute(
            sa.text(
                'INSERT INTO credit_packs (id, name, credits, price_usd_cents, is_active, sort_order) '
                'SELECT CAST(:id AS uuid), :name, :credits, :cents, true, :sort_order '
                'WHERE NOT EXISTS (SELECT 1 FROM credit_packs WHERE credits = :credits AND price_usd_cents = :cents)'
            ).bindparams(id=str(uuid.uuid4()), name=name, credits=credits, cents=cents, sort_order=sort_order)
        )


def downgrade() -> None:
    _set_tier_costs(PREVIOUS_TIER_COSTS)
    for name, credits, cents, _ in PACKS:
        match = 'name = :name AND credits = :credits AND price_usd_cents = :cents'
        params = dict(name=name, credits=credits, cents=cents)
        # A pack someone already bought must survive (purchases reference it);
        # it's only switched off. Unused ones are removed.
        op.execute(
            sa.text(
                f'UPDATE credit_packs SET is_active = false WHERE {match} '
                'AND EXISTS (SELECT 1 FROM purchases WHERE purchases.credit_pack_id = credit_packs.id)'
            ).bindparams(**params)
        )
        op.execute(
            sa.text(
                f'DELETE FROM credit_packs WHERE {match} '
                'AND NOT EXISTS (SELECT 1 FROM purchases WHERE purchases.credit_pack_id = credit_packs.id)'
            ).bindparams(**params)
        )
