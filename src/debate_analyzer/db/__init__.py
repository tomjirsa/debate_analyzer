"""Database layer for the web app: models, session, and repository."""

from debate_analyzer.db.base import get_engine, get_session_factory, init_db
from debate_analyzer.db.models import (
    Base,
    Segment,
    SpeakerMapping,
    SpeakerProfile,
    Transcript,
)
from debate_analyzer.db.repository import TranscriptRepository

__all__ = [
    "Base",
    "Segment",
    "SpeakerMapping",
    "SpeakerProfile",
    "Transcript",
    "TranscriptRepository",
    "get_engine",
    "get_session_factory",
    "init_db",
]
