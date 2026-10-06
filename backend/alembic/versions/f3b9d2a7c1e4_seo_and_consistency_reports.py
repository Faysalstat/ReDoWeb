"""seo and consistency reports on generation outputs

Revision ID: f3b9d2a7c1e4
Revises: c4e8a2d6f1b9
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f3b9d2a7c1e4'
down_revision: Union[str, Sequence[str], None] = 'c4e8a2d6f1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'generation_outputs',
        sa.Column('seo_report', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'generation_outputs',
        sa.Column('consistency_report', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('generation_outputs', 'consistency_report')
    op.drop_column('generation_outputs', 'seo_report')
