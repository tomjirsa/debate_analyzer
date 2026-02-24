"""add transcript_llm_analysis

Revision ID: a1b2c3d4e5f6
Revises: dfa1712dd3e2
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "dfa1712dd3e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add transcript_llm_analysis table."""
    op.create_table(
        "transcript_llm_analysis",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("transcript_id", sa.String(length=36), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transcript_id"], ["transcript.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transcript_llm_analysis_transcript_id"),
        "transcript_llm_analysis",
        ["transcript_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove transcript_llm_analysis table."""
    op.drop_index(
        op.f("ix_transcript_llm_analysis_transcript_id"),
        table_name="transcript_llm_analysis",
    )
    op.drop_table("transcript_llm_analysis")
