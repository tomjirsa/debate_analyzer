"""Structured result schema for LLM transcript analysis."""

from __future__ import annotations

from typing import Any


def _get_list(
    data: dict[str, Any], key: str, default: list[Any] | None = None
) -> list[Any]:
    """Return data[key] if it is a list, else default or []."""
    val = data.get(key)
    if isinstance(val, list):
        return val
    return default if default is not None else []


def _get_list_str(data: dict[str, Any], key: str) -> list[str]:
    """Return data[key] as list of strings, or []."""
    val = data.get(key)
    if isinstance(val, list):
        return [str(x) for x in val]
    return []


class SpeakerContribution:
    """One speaker contribution record: id, summary, keywords."""

    __slots__ = ("id", "speaker_id_in_transcript", "summary", "keywords")

    def __init__(
        self,
        id: str,
        speaker_id_in_transcript: str,
        summary: str,
        keywords: list[str] | None = None,
    ) -> None:
        self.id = id
        self.speaker_id_in_transcript = speaker_id_in_transcript
        self.summary = summary
        self.keywords = keywords if keywords is not None else []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON."""
        return {
            "id": self.id,
            "speaker_id_in_transcript": self.speaker_id_in_transcript,
            "summary": self.summary,
            "keywords": list(self.keywords),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SpeakerContribution:
        """Parse from dict."""
        return cls(
            id=str(d.get("id", "")),
            speaker_id_in_transcript=str(d.get("speaker_id_in_transcript", "")),
            summary=str(d.get("summary", "")),
            keywords=_get_list_str(d, "keywords"),
        )


class LLMAnalysisResult:
    """Result of LLM analysis: speaker contributions only."""

    __slots__ = ("speaker_contributions",)

    def __init__(self, speaker_contributions: list[dict[str, Any]]) -> None:
        self.speaker_contributions = speaker_contributions

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON storage."""
        return {"speaker_contributions": self.speaker_contributions}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LLMAnalysisResult:
        """Parse from raw LLM output dict (e.g. parsed JSON)."""
        return cls(speaker_contributions=_get_list(d, "speaker_contributions"))
