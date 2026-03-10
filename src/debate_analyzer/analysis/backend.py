"""Inference backend abstraction for LLM analysis."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMBackend(Protocol):
    """Protocol for batch inference: generate_batch(prompts, max_tokens) -> list."""

    def generate(self, prompt: str, max_tokens: int = 2048) -> str:
        """Generate completion for the given prompt. Returns raw model output text."""
        ...

    def generate_batch(self, prompts: list[str], max_tokens: int = 2048) -> list[str]:
        """Generate completions for the given prompts. Same order as input."""
        ...


class MockLLMBackend:
    """Mock backend for tests: returns a single default response per prompt."""

    def __init__(self, default_response: str | None = None) -> None:
        """Optional default_response; if unset, returns minimal empty JSON."""
        self.default_response = default_response or (
            '{"main_topics": [], "topic_summaries": [], "speaker_contributions": []}'
        )
        self.call_count = 0

    def _response_for_prompt(self, prompt: str) -> str:
        """Return response for one prompt. Grammar correction returns segment text."""
        if "Correct only grammar" in prompt or "Corrected text:" in prompt:
            parts = prompt.split("---")
            if len(parts) >= 2:
                return parts[1].strip()
            return ""
        return self.default_response

    def generate(self, prompt: str, max_tokens: int = 2048) -> str:
        """Return response based on prompt (default or grammar-correction)."""
        self.call_count += 1
        return self._response_for_prompt(prompt)

    def generate_batch(self, prompts: list[str], max_tokens: int = 2048) -> list[str]:
        """Return one response per prompt."""
        self.call_count += len(prompts)
        return [self._response_for_prompt(p) for p in prompts]
