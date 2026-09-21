"""add generation_jobs scope column

Revision ID: 5f88f9acc922
Revises: 7139b8eec790
Create Date: 2026-09-17 14:40:37.639676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f88f9acc922'
down_revision: Union[str, Sequence[str], None] = '7139b8eec790'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "generation_jobs",
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="preview"),
    )
    op.create_index(
        "ix_generation_jobs_project_tier_scope",
        "generation_jobs",
        ["project_id", "tier", "scope"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_generation_jobs_project_tier_scope", table_name="generation_jobs")
    op.drop_column("generation_jobs", "scope")
