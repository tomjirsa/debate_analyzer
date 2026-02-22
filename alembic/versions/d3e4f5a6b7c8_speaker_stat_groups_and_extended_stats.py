"""speaker_stat_group, speaker_stat_definition, and extended transcript_speaker_stats

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-02-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stat group tables and extend transcript_speaker_stats."""
    op.create_table(
        "speaker_stat_group",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_speaker_stat_group_key"),
    )
    op.create_index(
        "ix_speaker_stat_group_key", "speaker_stat_group", ["key"], unique=True
    )

    op.create_table(
        "speaker_stat_definition",
        sa.Column("stat_key", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["speaker_stat_group.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("stat_key"),
    )

    # Seed groups (id 1..5)
    op.execute(
        sa.text("""
        INSERT INTO speaker_stat_group (id, key, label, sort_order)
        VALUES
            (1, 'overview', 'Overview', 0),
            (2, 'speaking_rate', 'Speaking rate & segment length', 1),
            (3, 'uninterrupted_talks', 'Uninterrupted talks', 2),
            (4, 'turn_taking', 'Turn-taking', 3),
            (5, 'relative_share', 'Relative share', 4)
        """)
    )
    # Seed stat definitions (transcript_count is aggregate-only, no DB column)
    op.execute(
        sa.text("""
        INSERT INTO speaker_stat_definition (stat_key, group_id, label, sort_order)
        VALUES
            ('total_seconds', 1, 'Total speaking time (sec)', 0),
            ('segment_count', 1, 'Segment count', 1),
            ('word_count', 1, 'Word count', 2),
            ('transcript_count', 1, 'Transcripts', 3),
            ('wpm', 2, 'Words per minute', 0),
            ('avg_segment_duration_sec', 2, 'Avg segment duration (sec)', 1),
            ('shortest_talk_sec', 3, 'Shortest talk (sec)', 0),
            ('longest_talk_sec', 3, 'Longest talk (sec)', 1),
            ('median_segment_duration_sec', 3, 'Median segment duration (sec)', 2),
            ('turn_count', 4, 'Turn count', 0),
            ('avg_turn_length_sec', 4, 'Avg turn length (sec)', 1),
            ('avg_turn_length_segments', 4, 'Avg turn length (segments)', 2),
            ('is_first_speaker', 4, 'First speaker', 3),
            ('is_last_speaker', 4, 'Last speaker', 4),
            ('share_speaking_time', 5, 'Share of speaking time', 0),
            ('share_words', 5, 'Share of words', 1)
        """)
    )

    # Extend transcript_speaker_stats
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("wpm", sa.Float(), nullable=True),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("avg_segment_duration_sec", sa.Float(), nullable=True),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("shortest_talk_sec", sa.Float(), nullable=True),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("longest_talk_sec", sa.Float(), nullable=True),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("median_segment_duration_sec", sa.Float(), nullable=True),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("turn_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("avg_turn_length_sec", sa.Float(), nullable=True),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("avg_turn_length_segments", sa.Float(), nullable=True),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("is_first_speaker", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("is_last_speaker", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("share_speaking_time", sa.Float(), nullable=True),
    )
    op.add_column(
        "transcript_speaker_stats",
        sa.Column("share_words", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Remove new columns and drop stat definition tables."""
    op.drop_column("transcript_speaker_stats", "share_words")
    op.drop_column("transcript_speaker_stats", "share_speaking_time")
    op.drop_column("transcript_speaker_stats", "is_last_speaker")
    op.drop_column("transcript_speaker_stats", "is_first_speaker")
    op.drop_column("transcript_speaker_stats", "avg_turn_length_segments")
    op.drop_column("transcript_speaker_stats", "avg_turn_length_sec")
    op.drop_column("transcript_speaker_stats", "turn_count")
    op.drop_column("transcript_speaker_stats", "median_segment_duration_sec")
    op.drop_column("transcript_speaker_stats", "longest_talk_sec")
    op.drop_column("transcript_speaker_stats", "shortest_talk_sec")
    op.drop_column("transcript_speaker_stats", "avg_segment_duration_sec")
    op.drop_column("transcript_speaker_stats", "wpm")

    op.drop_table("speaker_stat_definition")
    op.drop_index("ix_speaker_stat_group_key", table_name="speaker_stat_group")
    op.drop_table("speaker_stat_group")
