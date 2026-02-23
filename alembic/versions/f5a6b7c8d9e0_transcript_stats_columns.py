"""transcript stats_total_words and stats_segment_count

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-02-23 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add stats_total_words and stats_segment_count to transcript."""
    op.add_column(
        "transcript",
        sa.Column("stats_total_words", sa.Integer(), nullable=True),
    )
    op.add_column(
        "transcript",
        sa.Column("stats_segment_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove stats columns from transcript."""
    op.drop_column("transcript", "stats_segment_count")
    op.drop_column("transcript", "stats_total_words")
