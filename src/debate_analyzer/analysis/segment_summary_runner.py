"""Segment-summary runner: per-block summary + keywords; split-then-merge for long."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from debate_analyzer.analysis.chunking import estimate_tokens, split_into_chunks
from debate_analyzer.analysis.prompts import (
    build_json_retry_prompt,
    build_merge_summaries_prompt,
    build_segment_summary_prompt,
)

logger = logging.getLogger(__name__)

# Reserve tokens for single-segment prompt + JSON reply
DEFAULT_RESERVE_SEGMENT_TOKENS = 2000
# Reserve tokens for merge prompt + JSON reply
DEFAULT_RESERVE_MERGE_TOKENS = 1000
# Overlap when splitting long segments
DEFAULT_OVERLAP_TOKENS = 100

_RAW_SNIPPET_MAX = 500


def _strip_markdown_json_fence(raw: str) -> str:
    """Remove leading/trailing ``` or ```json fences if present."""
    s = (raw or "").strip()
    if not s.startswith("```"):
        return s
    lines = s.split("\n")
    if not lines:
        return s
    if lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_summary_json(raw: str, *, log_context: str = "") -> tuple[str, list[str]]:
    """Extract summary and keywords from LLM response (JSON object).

    Requires top-level keys ``summary`` (non-empty string) and ``keywords`` (list).
    Does not accept Czech key names such as ``shrnutí`` in place of ``summary``.

    Tolerates surrounding text and markdown code blocks. Returns ("", []) on
    failure and logs a short warning with a capped raw prefix.

    Args:
        raw: Raw model output.
        log_context: Optional label included in log lines (e.g. segment index).

    Returns:
        ``(summary, keywords)``; both empty when validation or parse fails.
    """
    prefix = f"{log_context}: " if log_context else ""
    snippet = ((raw or "").replace("\n", " "))[:_RAW_SNIPPET_MAX]
    text = _strip_markdown_json_fence((raw or "").strip())
    # Try to find JSON object (first { to matching })
    start = text.find("{")
    if start == -1:
        logger.warning(
            "%ssegment_summary_json_parse: no_json_object raw_prefix=%r",
            prefix,
            snippet,
        )
        return "", []
    depth = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        logger.warning(
            "%ssegment_summary_json_parse: unbalanced_braces raw_prefix=%r",
            prefix,
            snippet,
        )
        return "", []
    try:
        data = json.loads(text[start:end])
    except json.JSONDecodeError as e:
        logger.warning(
            "%ssegment_summary_json_parse: json_decode_error %s raw_prefix=%r",
            prefix,
            e,
            snippet,
        )
        return "", []
    if not isinstance(data, dict):
        logger.warning(
            "%ssegment_summary_json_parse: not_a_dict raw_prefix=%r",
            prefix,
            snippet,
        )
        return "", []

    if "summary" not in data:
        if "shrnutí" in data or "shrnuti" in data:
            logger.warning(
                "%ssegment_summary_json_parse: wrong_keys_shrnuti raw_prefix=%r",
                prefix,
                snippet,
            )
        else:
            logger.warning(
                "%ssegment_summary_json_parse: missing_summary_key raw_prefix=%r",
                prefix,
                snippet,
            )
        return "", []

    summary = str(data.get("summary", "")).strip()
    if not summary:
        logger.warning(
            "%ssegment_summary_json_parse: empty_summary raw_prefix=%r",
            prefix,
            snippet,
        )
        return "", []

    if "keywords" not in data:
        logger.warning(
            "%ssegment_summary_json_parse: missing_keywords_key raw_prefix=%r",
            prefix,
            snippet,
        )
        keywords: list[str] = []
    else:
        kw = data.get("keywords")
        if isinstance(kw, list):
            keywords = [str(x).strip() for x in kw if str(x).strip()]
        else:
            logger.warning(
                "%ssegment_summary_json_parse: keywords_not_list raw_prefix=%r",
                prefix,
                snippet,
            )
            keywords = []

    return summary, keywords


def _one_json_summary_with_retry(
    primary_prompt: str,
    generate_batch: Callable[..., list[str]],
    max_tokens_per_reply: int,
    *,
    log_context: str,
) -> tuple[str, list[str], str]:
    """One segment/merge prompt: JSON mode, optional single JSON-only retry.

    Returns:
        Tuple of (summary, keywords, raw_model_text_from_last_attempt_used).
    """
    raw = generate_batch(
        [primary_prompt], max_tokens=max_tokens_per_reply, json_mode=True
    )[0]
    summary, keywords = _parse_summary_json(raw, log_context=log_context)
    if summary:
        return summary, keywords, raw

    logger.warning(
        "%ssegment_summary: retrying_once_after_failed_parse", log_context or "."
    )
    raw2 = generate_batch(
        [build_json_retry_prompt(primary_prompt)],
        max_tokens=max_tokens_per_reply,
        json_mode=True,
    )[0]
    summary, keywords = _parse_summary_json(raw2, log_context=f"{log_context} retry")
    return summary, keywords, raw2


def run_single_segment_summary(
    prompt: str,
    generate_batch: Callable[..., list[str]],
    max_tokens_per_reply: int = 2048,
    *,
    log_context: str = "single_segment",
) -> tuple[str, list[str], str]:
    """Run one segment-summary prompt with JSON parse and one retry on failure.

    Uses the same path as :func:`run_segment_summaries` for a single block (JSON
    mode, :func:`build_json_retry_prompt` on parse failure).

    Args:
        prompt: Full user prompt (e.g. built from a template with segment text).
        generate_batch: Backend ``(prompts, max_tokens, *, json_mode=False)``.
        max_tokens_per_reply: Max tokens for each LLM reply.
        log_context: Label for parse/retry logging.

    Returns:
        Tuple of ``(summary, keywords, raw_model_text_from_last_attempt)``.
    """
    return _one_json_summary_with_retry(
        prompt,
        generate_batch,
        max_tokens_per_reply,
        log_context=log_context,
    )


def run_segment_summaries(
    payload: dict[str, Any],
    generate_batch: Callable[..., list[str]],
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
        generate_batch: Backend ``(prompts, max_tokens, *, json_mode=False)``.
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
        ctx = f"segment idx={idx + 1} uid={uid[:8]}"

        if n_tokens <= max_input_tokens:
            # Single LLM call
            prompt = build_segment_summary_prompt(text)
            if log_progress:
                short_uid = uid[:8] + "..." if len(uid) > 8 else uid
                log_progress(f"Segment {idx + 1}: one call (uid={short_uid})")

            summary, keywords, raw_resp = _one_json_summary_with_retry(
                prompt,
                generate_batch,
                max_tokens_per_reply,
                log_context=ctx,
            )
            if log_llm_call:
                log_llm_call("segment_summary", prompt, raw_resp)

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
        partials: list[tuple[str, list[str]]] = []
        for ci, p in enumerate(prompts):
            s, k, chunk_raw = _one_json_summary_with_retry(
                p,
                generate_batch,
                max_tokens_per_reply,
                log_context=f"{ctx} chunk={ci + 1}",
            )
            partials.append((s, k))
            if log_llm_call:
                log_llm_call(f"segment_chunk_{ci}", p, chunk_raw)

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
        summary, keywords, merge_raw = _one_json_summary_with_retry(
            merge_prompt,
            generate_batch,
            max_tokens_per_reply,
            log_context=f"{ctx} merge",
        )
        if log_llm_call:
            log_llm_call("segment_merge", merge_prompt, merge_raw)

        if not summary and partials:
            # Fallback: concat first/last summary, merge keyword lists
            summary = " ".join(p[0] for p in partials if p[0]).strip() or ""
            seen_terms: set[str] = set()
            for _sum_part, kw_list in partials:
                for term in kw_list:
                    if term and term not in seen_terms:
                        seen_terms.add(term)
            keywords = list(seen_terms)

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
