"""project brand assets (logo / hero uploaded at submission)

Audit columns only -- the files themselves live on disk under
projects/{id}/brand_assets/ (services/brand_assets_service.py).

Revision ID: e7b1c4d9a2f6
Revises: d4a7c2e9f1b3
Create Date: 2026-11-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b1c4d9a2f6'
down_revision: Union[str, Sequence[str], None] = 'd4a7c2e9f1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projects', sa.Column('brand_logo_path', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('brand_hero_path', sa.Text(), nullable=True))
    op.add_column(
        'projects',
        sa.Column('brand_assets_later', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'brand_assets_later')
    op.drop_column('projects', 'brand_hero_path')
    op.drop_column('projects', 'brand_logo_path')
