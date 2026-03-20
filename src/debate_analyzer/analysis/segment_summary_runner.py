"""Segment-summary runner: per-block summary + keywords; split-then-merge for long."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from debate_analyzer.analysis.chunking import estimate_tokens, split_into_chunks
from debate_analyzer.analysis.prompts import (
    build_merge_summaries_prompt,
    build_segment_summary_prompt,
)

# Reserve tokens for single-segment prompt + JSON reply
DEFAULT_RESERVE_SEGMENT_TOKENS = 2000
# Reserve tokens for merge prompt + JSON reply
DEFAULT_RESERVE_MERGE_TOKENS = 1000
# Overlap when splitting long segments
DEFAULT_OVERLAP_TOKENS = 100


def _parse_summary_json(raw: str) -> tuple[str, list[str]]:
    """Extract summary and keywords from LLM response (JSON).

    Tolerates surrounding text and markdown code blocks.
    Returns ("", []) on parse failure.
    """
    raw = (raw or "").strip()
    # Try to find JSON object (first { to matching })
    start = raw.find("{")
    if start == -1:
        return "", []
    depth = 0
    end = -1
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return "", []
    try:
        data = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return "", []
    summary = str(data.get("summary", "")).strip()
    kw = data.get("keywords")
    if isinstance(kw, list):
        keywords = [str(x).strip() for x in kw if str(x).strip()]
    else:
        keywords = []
    return summary, keywords


def run_segment_summaries(
    payload: dict[str, Any],
    generate_batch: Callable[[list[str], int], list[str]],
    max_context_tokens: int = 6000,
    reserve_segment_tokens: int = DEFAULT_RESERVE_SEGMENT_TOKENS,
    reserve_merge_tokens: int = DEFAULT_RESERVE_MERGE_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    token_counter: Callable[[str], int] | None = None,
    max_tokens_per_reply: int = 2048,
    min_words: int = 0,
    log_progress: Callable[[str], None] | None = None,
    log_llm_call: Callable[[str, str, str], None] | None = None,
) -> list[dict[str, Any]]:
    """Produce one summary + keywords per block; long blocks use split-then-merge.

    Segments with fewer than min_words (by word count) are skipped and do not
    appear in the returned list.

    Args:
        payload: Transcript dict with "transcription" key (list of blocks).
        generate_batch: Backend callable(prompts, max_tokens) -> list[str].
        max_context_tokens: Total context size for the model.
        reserve_segment_tokens: Tokens reserved for prompt + output for one segment.
        reserve_merge_tokens: Tokens reserved for merge prompt + output.
        overlap_tokens: Overlap when splitting long segment text.
        token_counter: Token count function; if None, uses estimate_tokens.
        max_tokens_per_reply: Max tokens for each LLM reply.
        min_words: Minimum word count for a segment to be summarized; segments
            with fewer words are skipped (default 0 = no minimum).
        log_progress: Optional progress callback.
        log_llm_call: Optional (label, prompt, response) callback.

    Returns:
        List of dicts (uid, speaker, start, end, summary, keywords); transcript order.
    """
    count = token_counter or estimate_tokens
    transcription = payload.get("transcription") or []
    results: list[dict[str, Any]] = []

    for idx, block in enumerate(transcription):
        uid = block.get("uid") or ""
        speaker = block.get("speaker") or "SPEAKER_UNKNOWN"
        text = (block.get("text") or "").strip()
        start = block.get("start")
        end = block.get("end")
        try:
            start_f = float(start) if start is not None else 0.0
        except (TypeError, ValueError):
            start_f = 0.0
        try:
            end_f = float(end) if end is not None else 0.0
        except (TypeError, ValueError):
            end_f = 0.0

        if not text:
            if log_progress:
                log_progress(f"Segment {idx + 1}: empty text, skipping")
            continue

        if min_words > 0 and len(text.split()) < min_words:
            if log_progress:
                log_progress(
                    f"Segment {idx + 1}: below min_words={min_words}, skipping"
                )
            continue

        max_input_tokens = max(500, max_context_tokens - reserve_segment_tokens)
        n_tokens = count(text)

        if n_tokens <= max_input_tokens:
            # Single LLM call
            prompt = build_segment_summary_prompt(text)
            if log_progress:
                short_uid = uid[:8] + "..." if len(uid) > 8 else uid
                log_progress(f"Segment {idx + 1}: one call (uid={short_uid})")
            responses = generate_batch([prompt], max_tokens=max_tokens_per_reply)
            if log_llm_call and responses:
                log_llm_call("segment_summary", prompt, responses[0])
            summary, keywords = (
                _parse_summary_json(responses[0]) if responses else ("", [])
            )
            results.append(
                {
                    "uid": uid,
                    "speaker": speaker,
                    "start": start_f,
                    "end": end_f,
                    "summary": summary,
                    "keywords": keywords,
                }
            )
            continue

        # Split then merge
        chunks = split_into_chunks(
            text,
            max_tokens=max_input_tokens,
            overlap_tokens=overlap_tokens,
            token_counter=count,
        )
        if not chunks:
            results.append(
                {
                    "uid": uid,
                    "speaker": speaker,
                    "start": start_f,
                    "end": end_f,
                    "summary": "",
                    "keywords": [],
                }
            )
            continue

        if log_progress:
            log_progress(
                f"Segment {idx + 1}: {len(chunks)} chunks + merge (uid={uid[:8]}...)"
            )

        prompts = [build_segment_summary_prompt(c) for c in chunks]
        responses = generate_batch(prompts, max_tokens=max_tokens_per_reply)
        if log_llm_call:
            for i, (p, r) in enumerate(zip(prompts, responses)):
                log_llm_call(f"segment_chunk_{i}", p, r)

        partials: list[tuple[str, list[str]]] = []
        for r in responses:
            summary, keywords = _parse_summary_json(r)
            partials.append((summary, keywords))

        if not partials:
            results.append(
                {
                    "uid": uid,
                    "speaker": speaker,
                    "start": start_f,
                    "end": end_f,
                    "summary": "",
                    "keywords": [],
                }
            )
            continue

        if len(partials) == 1:
            s, k = partials[0]
            results.append(
                {
                    "uid": uid,
                    "speaker": speaker,
                    "start": start_f,
                    "end": end_f,
                    "summary": s,
                    "keywords": k,
                }
            )
            continue

        merge_prompt = build_merge_summaries_prompt(partials)
        merge_responses = generate_batch(
            [merge_prompt],
            max_tokens=max_tokens_per_reply,
        )
        if log_llm_call and merge_responses:
            log_llm_call("segment_merge", merge_prompt, merge_responses[0])

        summary, keywords = (
            _parse_summary_json(merge_responses[0]) if merge_responses else ("", [])
        )
        if not summary and partials:
            # Fallback: concat first/last summary, merge keyword lists
            summary = " ".join(p[0] for p in partials if p[0]).strip() or ""
            seen: set[str] = set()
            for _, kws in partials:
                for k in kws:
                    if k and k not in seen:
                        seen.add(k)
            keywords = list(seen)

        results.append(
            {
                "uid": uid,
                "speaker": speaker,
                "start": start_f,
                "end": end_f,
                "summary": summary,
                "keywords": keywords,
            }
        )

    return results
