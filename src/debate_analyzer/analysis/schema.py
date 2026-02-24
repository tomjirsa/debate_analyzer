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


class TopicSummary:
    """Summary of discussion for one topic."""

    __slots__ = ("topic_id", "summary")

    def __init__(self, topic_id: str, summary: str) -> None:
        self.topic_id = topic_id
        self.summary = summary

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON."""
        return {"topic_id": self.topic_id, "summary": self.summary}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TopicSummary:
        """Parse from dict."""
        return cls(
            topic_id=str(d.get("topic_id", "")),
            summary=str(d.get("summary", "")),
        )


class SpeakerContribution:
    """One speaker's contribution summary for one topic."""

    __slots__ = ("topic_id", "speaker_id_in_transcript", "summary")

    def __init__(
        self,
        topic_id: str,
        speaker_id_in_transcript: str,
        summary: str,
    ) -> None:
        self.topic_id = topic_id
        self.speaker_id_in_transcript = speaker_id_in_transcript
        self.summary = summary

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON."""
        return {
            "topic_id": self.topic_id,
            "speaker_id_in_transcript": self.speaker_id_in_transcript,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SpeakerContribution:
        """Parse from dict."""
        return cls(
            topic_id=str(d.get("topic_id", "")),
            speaker_id_in_transcript=str(d.get("speaker_id_in_transcript", "")),
            summary=str(d.get("summary", "")),
        )


class LLMAnalysisResult:
    """Full result of LLM analysis: topics, topic summaries, speaker contributions."""

    __slots__ = ("main_topics", "topic_summaries", "speaker_contributions")

    def __init__(
        self,
        main_topics: list[dict[str, Any]],
        topic_summaries: list[dict[str, Any]],
        speaker_contributions: list[dict[str, Any]],
    ) -> None:
        self.main_topics = main_topics
        self.topic_summaries = topic_summaries
        self.speaker_contributions = speaker_contributions

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON storage."""
        return {
            "main_topics": self.main_topics,
            "topic_summaries": self.topic_summaries,
            "speaker_contributions": self.speaker_contributions,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LLMAnalysisResult:
        """Parse from raw LLM output dict (e.g. parsed JSON)."""
        return cls(
            main_topics=_get_list(d, "main_topics"),
            topic_summaries=_get_list(d, "topic_summaries"),
            speaker_contributions=_get_list(d, "speaker_contributions"),
        )
