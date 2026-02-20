"""transcript_speaker_stats table

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-02-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create transcript_speaker_stats table."""
    op.create_table(
        "transcript_speaker_stats",
        sa.Column("transcript_id", sa.String(length=36), nullable=False),
        sa.Column("speaker_id_in_transcript", sa.String(length=64), nullable=False),
        sa.Column("total_seconds", sa.Float(), nullable=False),
        sa.Column("segment_count", sa.Integer(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transcript_id"],
            ["transcript.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("transcript_id", "speaker_id_in_transcript"),
        sa.UniqueConstraint(
            "transcript_id",
            "speaker_id_in_transcript",
            name="uq_transcript_speaker_stats",
        ),
    )


def downgrade() -> None:
    """Drop transcript_speaker_stats table."""
    op.drop_table("transcript_speaker_stats")
