"""speaker_profile first_name surname short_description

Revision ID: b1c2d3e4f5a6
Revises: ea2adb546043
Create Date: 2026-02-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "ea2adb546043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace display_name with first_name, surname; add short_description."""
    # Add new columns as nullable first
    op.add_column(
        "speaker_profile",
        sa.Column("first_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "speaker_profile",
        sa.Column("surname", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "speaker_profile",
        sa.Column("short_description", sa.Text(), nullable=True),
    )

    # Backfill: split display_name into first_name and surname (first token vs rest)
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text("""
                UPDATE speaker_profile
                SET first_name = CASE
                    WHEN INSTR(COALESCE(display_name, '') || ' ', ' ') > 0
                    THEN SUBSTR(COALESCE(display_name, '') || ' ', 1, INSTR(COALESCE(display_name, '') || ' ', ' ') - 1)
                    ELSE COALESCE(display_name, '')
                END,
                surname = CASE
                    WHEN INSTR(COALESCE(display_name, '') || ' ', ' ') > 0
                    THEN TRIM(SUBSTR(COALESCE(display_name, '') || ' ', INSTR(COALESCE(display_name, '') || ' ', ' ') + 1))
                    ELSE ''
                END
            """)
        )
    else:
        # PostgreSQL: first word = first_name, rest = surname
        conn.execute(
            sa.text("""
                UPDATE speaker_profile
                SET
                    first_name = COALESCE(SPLIT_PART(TRIM(COALESCE(display_name, '')) || ' ', ' ', 1), ''),
                    surname = COALESCE(TRIM(SUBSTRING(TRIM(COALESCE(display_name, '')) || ' ' FROM LENGTH(SPLIT_PART(TRIM(COALESCE(display_name, '')) || ' ', ' ', 1)) + 2)), '')
            """)
        )

    # Ensure no nulls remain
    conn.execute(
        sa.text("UPDATE speaker_profile SET first_name = '' WHERE first_name IS NULL")
    )
    conn.execute(
        sa.text("UPDATE speaker_profile SET surname = '' WHERE surname IS NULL")
    )

    # Make columns NOT NULL
    if conn.dialect.name == "sqlite":
        # SQLite does not support ALTER COLUMN; recreate table or use batch
        with op.batch_alter_table("speaker_profile", schema=None) as batch_op:
            batch_op.alter_column(
                "first_name",
                existing_type=sa.String(255),
                nullable=False,
            )
            batch_op.alter_column(
                "surname",
                existing_type=sa.String(255),
                nullable=False,
            )
    else:
        op.alter_column(
            "speaker_profile",
            "first_name",
            existing_type=sa.String(255),
            nullable=False,
        )
        op.alter_column(
            "speaker_profile",
            "surname",
            existing_type=sa.String(255),
            nullable=False,
        )

    # Drop display_name
    op.drop_column("speaker_profile", "display_name")


def downgrade() -> None:
    """Restore display_name; drop first_name, surname, short_description."""
    op.add_column(
        "speaker_profile",
        sa.Column("display_name", sa.String(length=255), nullable=True),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE speaker_profile
            SET display_name = TRIM(COALESCE(first_name, '') || ' ' || COALESCE(surname, ''))
        """)
    )

    if conn.dialect.name != "sqlite":
        op.alter_column(
            "speaker_profile",
            "display_name",
            existing_type=sa.String(255),
            nullable=False,
        )

    op.drop_column("speaker_profile", "short_description")
    op.drop_column("speaker_profile", "surname")
    op.drop_column("speaker_profile", "first_name")
