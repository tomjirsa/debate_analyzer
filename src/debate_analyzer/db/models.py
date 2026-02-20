"""SQLAlchemy models for speaker profiles, transcripts, mappings, and segments."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid():
    return str(uuid.uuid4())


class SpeakerProfile(Base):
    """Canonical speaker (person) that can appear in multiple transcripts."""

    __tablename__ = "speaker_profile"

    id = Column(String(36), primary_key=True, default=_uuid)
    display_name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=True, index=True)
    bio = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mappings = relationship("SpeakerMapping", back_populates="speaker_profile")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API responses."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "slug": self.slug,
            "bio": self.bio,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Transcript(Base):
    """One transcript (e.g. one S3 object or Batch job output)."""

    __tablename__ = "transcript"

    id = Column(String(36), primary_key=True, default=_uuid)
    source_type = Column(String(64), nullable=False, default="s3")
    source_uri = Column(String(1024), nullable=False, unique=True, index=True)
    title = Column(String(512), nullable=True)
    duration = Column(Float, nullable=True)
    video_path = Column(String(1024), nullable=True)
    speakers_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column("metadata", JSON, nullable=True)

    segments = relationship(
        "Segment", back_populates="transcript", cascade="all, delete-orphan"
    )
    speaker_mappings = relationship(
        "SpeakerMapping", back_populates="transcript", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API responses."""
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "title": self.title,
            "duration": self.duration,
            "video_path": self.video_path,
            "speakers_count": self.speakers_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata_,
        }


class SpeakerMapping(Base):
    """Maps a transcript's diarization label (e.g. SPEAKER_00) to a speaker profile."""

    __tablename__ = "speaker_mapping"
    __table_args__ = (
        UniqueConstraint(
            "transcript_id", "speaker_id_in_transcript", name="uq_transcript_speaker"
        ),
    )

    transcript_id = Column(
        String(36), ForeignKey("transcript.id", ondelete="CASCADE"), primary_key=True
    )
    speaker_id_in_transcript = Column(String(64), primary_key=True)  # e.g. SPEAKER_00
    speaker_profile_id = Column(
        String(36), ForeignKey("speaker_profile.id", ondelete="CASCADE"), nullable=True
    )

    transcript = relationship("Transcript", back_populates="speaker_mappings")
    speaker_profile = relationship("SpeakerProfile", back_populates="mappings")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API responses."""
        return {
            "transcript_id": self.transcript_id,
            "speaker_id_in_transcript": self.speaker_id_in_transcript,
            "speaker_profile_id": self.speaker_profile_id,
        }


class Segment(Base):
    """One segment (start, end, text, speaker). Stored for fast stats."""

    __tablename__ = "segment"

    id = Column(String(36), primary_key=True, default=_uuid)
    transcript_id = Column(
        String(36),
        ForeignKey("transcript.id", ondelete="CASCADE"),
        nullable=False,
    )
    start = Column(Float, nullable=False)
    end = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    speaker_id_in_transcript = Column(String(64), nullable=False)
    confidence = Column(Float, nullable=True)

    transcript = relationship("Transcript", back_populates="segments")
