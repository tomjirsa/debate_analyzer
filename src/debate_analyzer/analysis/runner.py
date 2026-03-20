"""Orchestrate LLM analysis.

This runs per-segment summaries and then aggregates them into:
- `speaker_contributions`: one merged summary per speaker
- `transcript_summary`: one merged summary for the whole transcript
"""

from __future__ import annotations

from typing import Any, Callable

from debate_analyzer.analysis.prompts import build_merge_summaries_prompt
from debate_analyzer.analysis.segment_summary_runner import (
    _parse_summary_json,
    run_segment_summaries,
)


def run_analysis(
    payload: dict[str, Any],
    generate_batch: Callable[[list[str], int], list[str]],
    max_context_tokens: int = 24_000,
    max_excerpt_tokens: int | None = None,
    token_counter: Callable[[str], int] | None = None,
    max_tokens_per_reply: int = 2048,
    min_words: int = 0,
    log_progress: Callable[[str], None] | None = None,
    log_llm_call: Callable[[str, str, str], None] | None = None,
) -> dict[str, Any]:
    """
    Run segment-summary analysis and aggregate results.

    Uses split-then-merge for blocks whose text exceeds the context budget.
    Result shape:
        {
          "segment_summaries": [
            { "uid", "speaker", "start", "end", "summary", "keywords" }, ...
          ],
          "speaker_contributions": [
            { "id", "speaker_id_in_transcript", "summary", "keywords" }, ...
          ],
          "transcript_summary": { "summary": str, "keywords": [str, ...] },
        }

    Args:
        payload: Transcript dict with "transcription" (list of blocks with
            uid, speaker, text, start, end).
        generate_batch: Backend callable(prompts, max_tokens) -> list[str].
        max_context_tokens: Max context size for the model.
        max_excerpt_tokens: Unused (kept for API compatibility).
        token_counter: Token count function; if None, uses estimate_tokens.
        max_tokens_per_reply: Max tokens per LLM reply.
        min_words: Minimum word count for a segment to be summarized (default 0).
        log_progress: Optional progress callback.
        log_llm_call: Optional (label, prompt, response) callback.

    Returns:
        Dict with keys "segment_summaries", "speaker_contributions",
        and "transcript_summary".
    """
    _ = max_excerpt_tokens
    segment_summaries = run_segment_summaries(
        payload=payload,
        generate_batch=generate_batch,
        max_context_tokens=max_context_tokens,
        token_counter=token_counter,
        max_tokens_per_reply=max_tokens_per_reply,
        min_words=min_words,
        log_progress=log_progress,
        log_llm_call=log_llm_call,
    )

    # Aggregate per-speaker contributions from segment summaries.
    speaker_order: list[str] = []
    speaker_partials: dict[str, list[tuple[str, list[str]]]] = {}
    for seg in segment_summaries:
        speaker = str(seg.get("speaker") or "SPEAKER_UNKNOWN")
        if speaker not in speaker_partials:
            speaker_order.append(speaker)
            speaker_partials[speaker] = []

        summary = str(seg.get("summary") or "").strip()
        if not summary:
            continue

        raw_keywords = seg.get("keywords") or []
        if isinstance(raw_keywords, list):
            keywords = [str(x).strip() for x in raw_keywords if str(x).strip()]
        else:
            keywords = []
        speaker_partials[speaker].append((summary, keywords))

    speaker_contributions: list[dict[str, Any]] = []
    for speaker in speaker_order:
        partials = speaker_partials.get(speaker) or []
        if not partials:
            continue

        if len(partials) == 1:
            merged_summary, merged_keywords = partials[0]
        else:
            merge_prompt = build_merge_summaries_prompt(partials)
            responses = generate_batch([merge_prompt], max_tokens=max_tokens_per_reply)
            if log_llm_call and responses:
                log_llm_call("speaker_merge", merge_prompt, responses[0])
            merged_summary, merged_keywords = (
                _parse_summary_json(responses[0]) if responses else ("", [])
            )

        speaker_contributions.append(
            {
                "id": f"speaker_summary:{speaker}",
                "speaker_id_in_transcript": speaker,
                "summary": merged_summary,
                "keywords": merged_keywords,
            }
        )

    # Aggregate a transcript-level summary from merged speaker summaries.
    transcript_summary: dict[str, Any] = {"summary": "", "keywords": []}
    transcript_partials: list[tuple[str, list[str]]] = []
    for c in speaker_contributions:
        s = str(c.get("summary") or "").strip()
        if not s:
            continue
        raw_keywords = c.get("keywords") or []
        keywords = (
            [str(x).strip() for x in raw_keywords if str(x).strip()]
            if isinstance(raw_keywords, list)
            else []
        )
        transcript_partials.append((s, keywords))

    if len(transcript_partials) == 1:
        transcript_summary["summary"] = transcript_partials[0][0]
        transcript_summary["keywords"] = transcript_partials[0][1]
    elif len(transcript_partials) > 1:
        merge_prompt = build_merge_summaries_prompt(transcript_partials)
        responses = generate_batch([merge_prompt], max_tokens=max_tokens_per_reply)
        if log_llm_call and responses:
            log_llm_call("transcript_merge", merge_prompt, responses[0])
        merged_summary, merged_keywords = (
            _parse_summary_json(responses[0]) if responses else ("", [])
        )
        transcript_summary = {"summary": merged_summary, "keywords": merged_keywords}

    return {
        "segment_summaries": segment_summaries,
        "speaker_contributions": speaker_contributions,
        "transcript_summary": transcript_summary,
    }
