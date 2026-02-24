"""add transcript description and debate_date

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add description and debate_date columns to transcript."""
    op.add_column(
        "transcript",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "transcript",
        sa.Column("debate_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    """Remove description and debate_date from transcript."""
    op.drop_column("transcript", "debate_date")
    op.drop_column("transcript", "description")
