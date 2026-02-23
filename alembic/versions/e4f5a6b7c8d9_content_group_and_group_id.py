"""content_group table and group_id on transcript, speaker_profile

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-02-23 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_GROUP_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Create content_group and add group_id to transcript and speaker_profile."""
    op.create_table(
        "content_group",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_content_group_slug"),
    )
    op.create_index(
        "ix_content_group_slug", "content_group", ["slug"], unique=True
    )

    op.add_column(
        "transcript",
        sa.Column("group_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "speaker_profile",
        sa.Column("group_id", sa.String(length=36), nullable=True),
    )

    op.execute(
        sa.text(
            "INSERT INTO content_group (id, name, slug, description) "
            "VALUES (:id, 'Default', 'default', 'Default group for existing data')"
        ).bindparams(id=DEFAULT_GROUP_ID)
    )

    op.execute(
        sa.text("UPDATE transcript SET group_id = :gid").bindparams(
            gid=DEFAULT_GROUP_ID
        )
    )
    op.execute(
        sa.text("UPDATE speaker_profile SET group_id = :gid").bindparams(
            gid=DEFAULT_GROUP_ID
        )
    )

    with op.batch_alter_table("transcript") as batch_op:
        batch_op.alter_column(
            "group_id",
            existing_type=sa.String(36),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_transcript_group_id",
            "content_group",
            ["group_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_transcript_group_id", ["group_id"], unique=False
        )

    with op.batch_alter_table("speaker_profile") as batch_op:
        batch_op.alter_column(
            "group_id",
            existing_type=sa.String(36),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_speaker_profile_group_id",
            "content_group",
            ["group_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_speaker_profile_group_id", ["group_id"], unique=False
        )
        batch_op.drop_index("ix_speaker_profile_slug")
        batch_op.create_index(
            "ix_speaker_profile_slug",
            ["slug"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_speaker_profile_group_slug",
            ["group_id", "slug"],
        )


def downgrade() -> None:
    """Remove group_id and content_group."""
    op.drop_constraint(
        "uq_speaker_profile_group_slug", "speaker_profile", type_="unique"
    )
    op.drop_index("ix_speaker_profile_slug", table_name="speaker_profile")
    op.create_index(
        "ix_speaker_profile_slug",
        "speaker_profile",
        ["slug"],
        unique=True,
    )

    op.drop_index("ix_speaker_profile_group_id", table_name="speaker_profile")
    op.drop_index("ix_transcript_group_id", table_name="transcript")
    op.drop_constraint(
        "fk_speaker_profile_group_id", "speaker_profile", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_transcript_group_id", "transcript", type_="foreignkey"
    )
    op.drop_column("speaker_profile", "group_id")
    op.drop_column("transcript", "group_id")

    op.drop_index("ix_content_group_slug", table_name="content_group")
    op.drop_table("content_group")
