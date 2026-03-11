"""Orchestrate LLM analysis: placeholder returns empty speaker contributions."""

from __future__ import annotations

from typing import Any, Callable

from debate_analyzer.analysis.schema import LLMAnalysisResult


def run_analysis(
    payload: dict[str, Any],
    generate_batch: Callable[[list[str], int], list[str]],
    max_context_tokens: int = 24_000,
    max_excerpt_tokens: int | None = None,
    token_counter: Callable[[str], int] | None = None,
    max_tokens_per_reply: int = 2048,
    log_progress: Callable[[str], None] | None = None,
    log_llm_call: Callable[[str, str, str], None] | None = None,
) -> dict[str, Any]:
    """
    Return empty analysis result (no LLM calls).

    Result schema: speaker_contributions only (list of contribution records with
    id, speaker_id_in_transcript, summary, keywords). generate_batch is not called.

    Args:
        payload: Transcript dict (optional: may contain "transcription" key).
        generate_batch: Backend callable; unused.
        max_context_tokens: Unused.
        max_excerpt_tokens: Unused.
        token_counter: Unused.
        max_tokens_per_reply: Unused.
        log_progress: Optional callback; unused.
        log_llm_call: Optional callback; unused.

    Returns:
        Dict with speaker_contributions=[].
    """
    _ = payload, generate_batch, max_context_tokens, max_excerpt_tokens
    _ = token_counter, max_tokens_per_reply, log_progress, log_llm_call
    return LLMAnalysisResult(speaker_contributions=[]).to_dict()
