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


class SegmentSummary:
    """One segment (block) summary: uid, speaker, start, end, summary, keywords."""

    __slots__ = ("uid", "speaker", "start", "end", "summary", "keywords")

    def __init__(
        self,
        uid: str,
        speaker: str,
        start: float,
        end: float,
        summary: str,
        keywords: list[str] | None = None,
    ) -> None:
        self.uid = uid
        self.speaker = speaker
        self.start = start
        self.end = end
        self.summary = summary
        self.keywords = keywords if keywords is not None else []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON."""
        return {
            "uid": self.uid,
            "speaker": self.speaker,
            "start": self.start,
            "end": self.end,
            "summary": self.summary,
            "keywords": list(self.keywords),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SegmentSummary:
        """Parse from dict."""

        def _float(val: Any) -> float:
            if val is None:
                return 0.0
            try:
                return float(val)
            except (TypeError, ValueError):
                return 0.0

        return cls(
            uid=str(d.get("uid", "")),
            speaker=str(d.get("speaker", "")),
            start=_float(d.get("start")),
            end=_float(d.get("end")),
            summary=str(d.get("summary", "")),
            keywords=_get_list_str(d, "keywords"),
        )


class LLMAnalysisResult:
    """Result of LLM analysis: speaker_contributions (legacy) or segment_summaries."""

    __slots__ = ("speaker_contributions", "segment_summaries")

    def __init__(
        self,
        speaker_contributions: list[dict[str, Any]] | None = None,
        segment_summaries: list[dict[str, Any]] | None = None,
    ) -> None:
        self.speaker_contributions = (
            speaker_contributions if speaker_contributions is not None else []
        )
        self.segment_summaries = (
            segment_summaries if segment_summaries is not None else []
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON storage."""
        out: dict[str, Any] = {}
        if self.speaker_contributions:
            out["speaker_contributions"] = self.speaker_contributions
        if self.segment_summaries:
            out["segment_summaries"] = self.segment_summaries
        if not out:
            out["segment_summaries"] = []
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LLMAnalysisResult:
        """Parse from raw LLM output dict (e.g. parsed JSON)."""
        return cls(
            speaker_contributions=_get_list(d, "speaker_contributions"),
            segment_summaries=_get_list(d, "segment_summaries"),
        )
