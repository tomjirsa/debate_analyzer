"""Data models for transcription and speaker diarization."""

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class TranscriptSegment:
    """A segment of transcribed text with timestamps."""

    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class SpeakerSegment:
    """A segment identified with a speaker label."""

    start: float
    end: float
    speaker_id: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class TranscriptWithSpeaker:
    """A transcribed segment with speaker identification."""

    start: float
    end: float
    text: str
    speaker: str
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
