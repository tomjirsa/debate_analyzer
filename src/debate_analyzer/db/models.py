"""SQLAlchemy models for speaker profiles, transcripts, mappings, and segments."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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
    first_name = Column(String(255), nullable=False)
    surname = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=True, index=True)
    bio = Column(Text, nullable=True)
    short_description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mappings = relationship("SpeakerMapping", back_populates="speaker_profile")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API responses."""
        display_name = f"{self.first_name} {self.surname}".strip()
        return {
            "id": self.id,
            "first_name": self.first_name,
            "surname": self.surname,
            "display_name": display_name,
            "slug": self.slug,
            "bio": self.bio,
            "short_description": self.short_description,
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
    speaker_stats = relationship(
        "TranscriptSpeakerStats",
        back_populates="transcript",
        cascade="all, delete-orphan",
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


class SpeakerStatGroup(Base):
    """Group of speaker stats for UI (e.g. Speaking rate, Turn-taking)."""

    __tablename__ = "speaker_stat_group"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    label = Column(String(255), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    stat_definitions = relationship(
        "SpeakerStatDefinition",
        back_populates="group",
        order_by="SpeakerStatDefinition.sort_order",
    )


class SpeakerStatDefinition(Base):
    """Definition of a single stat (key, label, group) for display."""

    __tablename__ = "speaker_stat_definition"

    stat_key = Column(String(64), primary_key=True)
    group_id = Column(
        Integer,
        ForeignKey("speaker_stat_group.id", ondelete="CASCADE"),
        nullable=False,
    )
    label = Column(String(255), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    group = relationship("SpeakerStatGroup", back_populates="stat_definitions")


class TranscriptSpeakerStats(Base):
    """Per-transcript, per-speaker stats (core + extended: wpm, turns, shares)."""

    __tablename__ = "transcript_speaker_stats"
    __table_args__ = (
        UniqueConstraint(
            "transcript_id",
            "speaker_id_in_transcript",
            name="uq_transcript_speaker_stats",
        ),
    )

    transcript_id = Column(
        String(36),
        ForeignKey("transcript.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    speaker_id_in_transcript = Column(String(64), primary_key=True, nullable=False)
    total_seconds = Column(Float, nullable=False)
    segment_count = Column(Integer, nullable=False)
    word_count = Column(Integer, nullable=False)
    wpm = Column(Float, nullable=True)
    avg_segment_duration_sec = Column(Float, nullable=True)
    shortest_talk_sec = Column(Float, nullable=True)
    longest_talk_sec = Column(Float, nullable=True)
    median_segment_duration_sec = Column(Float, nullable=True)
    turn_count = Column(Integer, nullable=True)
    avg_turn_length_sec = Column(Float, nullable=True)
    avg_turn_length_segments = Column(Float, nullable=True)
    is_first_speaker = Column(Boolean, nullable=False, default=False)
    is_last_speaker = Column(Boolean, nullable=False, default=False)
    share_speaking_time = Column(Float, nullable=True)
    share_words = Column(Float, nullable=True)

    transcript = relationship("Transcript", back_populates="speaker_stats")
