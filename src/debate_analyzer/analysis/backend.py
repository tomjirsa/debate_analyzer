"""Inference backend abstraction for LLM analysis."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMBackend(Protocol):
    """Protocol for generate(prompt, max_tokens) -> text."""

    def generate(self, prompt: str, max_tokens: int = 2048) -> str:
        """Generate completion for the given prompt. Returns raw model output text."""
        ...


class MockLLMBackend:
    """Mock backend for tests: returns fixed JSON-shaped strings."""

    def __init__(
        self,
        topics_response: str | None = None,
        summary_response: str | None = None,
        speaker_response: str | None = None,
    ) -> None:
        self.topics_response = topics_response or (
            '{"main_topics": [{"id": "t1", "title": "Topic A", "description": ""}]}'
        )
        self.summary_response = summary_response or (
            '{"topic_id": "t1", "summary": "Summary of discussion."}'
        )
        self.speaker_response = speaker_response or (
            '{"speaker_contributions": [{"topic_id": "t1", '
            '"speaker_id_in_transcript": "SPEAKER_00", "summary": "In favor."}]}'
        )
        self.call_count = 0

    def generate(self, prompt: str, max_tokens: int = 2048) -> str:
        """Return a canned response based on prompt content."""
        self.call_count += 1
        if "main_topics" in prompt or "List the main topics" in prompt:
            return self.topics_response
        if (
            "Summarize the outcome" in prompt
            or '"summary":' in prompt
            and "speaker_contributions" not in prompt
        ):
            return self.summary_response
        if "speaker_contributions" in prompt or "each speaker's position" in prompt:
            return self.speaker_response
        return self.topics_response
