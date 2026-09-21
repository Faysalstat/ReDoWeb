"""add reveal visibility fixes column

Revision ID: 7139b8eec790
Revises: 7ba9d237ac0b
Create Date: 2026-09-16 22:42:43.214680

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7139b8eec790'
down_revision: Union[str, Sequence[str], None] = '7ba9d237ac0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'generation_outputs',
        sa.Column('reveal_visibility_fixes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('generation_outputs', 'reveal_visibility_fixes')
