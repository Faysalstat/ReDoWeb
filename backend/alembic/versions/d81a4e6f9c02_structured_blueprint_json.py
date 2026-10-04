"""structured blueprint json

Revision ID: d81a4e6f9c02
Revises: c69f2b03d8a1
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd81a4e6f9c02'
down_revision: Union[str, Sequence[str], None] = 'c69f2b03d8a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('blueprints', sa.Column('tagline', sa.String(length=255), nullable=True))
    op.add_column('blueprints', sa.Column('favicon_path', sa.Text(), nullable=True))
    op.add_column('blueprints', sa.Column('scraped_json_storage_path', sa.Text(), nullable=True))
    op.add_column('blueprints', sa.Column('blueprint_json_storage_path', sa.Text(), nullable=True))
    op.alter_column('blueprints', 'design_md_storage_path', existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Note: this will fail if any row has a NULL design_md_storage_path by
    # the time this runs (expected for rows created after this migration
    # via the structured pipeline without the legacy-compat shim producing
    # a value) -- restore data or drop those rows before downgrading.
    op.alter_column('blueprints', 'design_md_storage_path', existing_type=sa.Text(), nullable=False)
    op.drop_column('blueprints', 'blueprint_json_storage_path')
    op.drop_column('blueprints', 'scraped_json_storage_path')
    op.drop_column('blueprints', 'favicon_path')
    op.drop_column('blueprints', 'tagline')
