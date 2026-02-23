"""Add photo_key to speaker_profile for S3/CloudFront profile photos.

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-02-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add photo_key column to speaker_profile."""
    op.add_column(
        "speaker_profile",
        sa.Column("photo_key", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    """Remove photo_key column from speaker_profile."""
    op.drop_column("speaker_profile", "photo_key")
