"""Orchestrate LLM analysis: segment summaries (per-block summary + keywords)."""

from __future__ import annotations

from typing import Any, Callable

from debate_analyzer.analysis.segment_summary_runner import run_segment_summaries


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
    Run segment-summary analysis: one summary + keywords per transcript block.

    Uses split-then-merge for blocks whose text exceeds the context budget.
    Result shape: { "segment_summaries": [ { uid, speaker, start, end, summary,
    keywords }, ... ] }.

    Args:
        payload: Transcript dict with "transcription" (list of blocks with
            uid, speaker, text, start, end).
        generate_batch: Backend callable(prompts, max_tokens) -> list[str].
        max_context_tokens: Max context size for the model.
        max_excerpt_tokens: Unused (kept for API compatibility).
        token_counter: Token count function; if None, uses estimate_tokens.
        max_tokens_per_reply: Max tokens per LLM reply.
        log_progress: Optional progress callback.
        log_llm_call: Optional (label, prompt, response) callback.

    Returns:
        Dict with key "segment_summaries" (list of segment summary dicts).
    """
    _ = max_excerpt_tokens
    segment_summaries = run_segment_summaries(
        payload=payload,
        generate_batch=generate_batch,
        max_context_tokens=max_context_tokens,
        token_counter=token_counter,
        max_tokens_per_reply=max_tokens_per_reply,
        log_progress=log_progress,
        log_llm_call=log_llm_call,
    )
    return {"segment_summaries": segment_summaries}
