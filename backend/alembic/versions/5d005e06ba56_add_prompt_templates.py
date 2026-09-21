"""add prompt_templates

Revision ID: 5d005e06ba56
Revises: e14eca398b7e
Create Date: 2026-09-20 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d005e06ba56'
down_revision: Union[str, Sequence[str], None] = 'e14eca398b7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    No backfill rows for the pre-existing static backend/prompts/*.txt
    files: a file present on disk with no row here is treated as active
    by prompt_template_service.get_active_template_filenames(). A legacy
    file only gets a real row the first time an admin explicitly disables
    or re-enables it (see prompt_template_service.set_active) -- this
    keeps the table from ever drifting out of sync with what's actually
    on disk.
    """
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('uploaded_by_admin_id', sa.UUID(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['uploaded_by_admin_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('filename'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('prompt_templates')
