"""Orchestrate LLM analysis: chunking, prompts, and result assembly."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from debate_analyzer.analysis.chunking import (
    DEFAULT_MAX_CHUNK_TOKENS,
    flatten_transcription_with_indices,
    get_topic_relevant_excerpt_with_range,
    split_into_chunks,
    topic_keywords,
)
from debate_analyzer.analysis.prompts import (
    build_topic_summary_and_contributions_prompt,
    build_topics_chunk_prompt,
)
from debate_analyzer.analysis.schema import LLMAnalysisResult


def _extract_json(text: str) -> dict[str, Any] | list[Any] | None:
    """Extract a JSON object or array from model output (may be wrapped in markdown)."""
    text = text.strip()
    result = _parse_json_once(text)
    if result is not None:
        return result
    # Retry after stripping markdown code fences
    stripped = re.sub(r"^```(?:json)?\s*", "", text)
    stripped = re.sub(r"\s*```\s*$", "", stripped)
    return _parse_json_once(stripped.strip())


def _parse_json_once(text: str) -> dict[str, Any] | list[Any] | None:
    """Find first { or [ and matching } or ], parse; return None on failure."""
    start_obj = text.find("{")
    start_arr = text.find("[")
    if start_obj >= 0 and (start_arr < 0 or start_obj < start_arr):
        start = start_obj
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        return None
    if start_arr >= 0:
        start = start_arr
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        return None
    return None


def _normalize_topic_title(title: str) -> str:
    """Normalize title for merge: strip parentheticals, collapse whitespace, lower."""
    s = (title or "").strip().lower()
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    s = re.sub(r"[\s\-–—]+", " ", s)
    return " ".join(s.split())


def _merge_topic_ids(topic_dicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate topics by normalized title; merge when one is prefix of another."""
    seen: dict[str, dict[str, Any]] = {}
    for t in topic_dicts:
        title = (t.get("title") or "").strip()
        if not title:
            continue
        n = _normalize_topic_title(title)
        merged = False
        for k in list(seen.keys()):
            if n.startswith(k) or k.startswith(n):
                if len(n) < len(k):
                    del seen[k]
                    seen[n] = dict(t)
                merged = True
                break
        if not merged:
            seen[n] = dict(t)
    result = []
    for i, (_, t) in enumerate(sorted(seen.items(), key=lambda x: x[0]), start=1):
        t["id"] = f"t{i}"
        result.append(t)
    return result


def _aggregate_speaker_contributions(
    speaker_contributions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Aggregate multiple contributions from the same speaker for the same topic into one.

    Groups by (topic_id, speaker_id_in_transcript), preserves order of first
    occurrence, and concatenates summary strings with a space.

    Args:
        speaker_contributions: List of dicts with topic_id, speaker_id_in_transcript,
            and summary.

    Returns:
        One dict per (topic_id, speaker_id_in_transcript) with combined summary.
    """
    key_order: list[tuple[str, str]] = []
    groups: dict[tuple[str, str], list[str]] = {}
    for sc in speaker_contributions:
        topic_id = str(sc.get("topic_id", "")).strip()
        speaker_id = str(sc.get("speaker_id_in_transcript", "")).strip()
        summary = str(sc.get("summary", "")).strip()
        key = (topic_id, speaker_id)
        if key not in groups:
            key_order.append(key)
            groups[key] = []
        if summary:
            groups[key].append(summary)
    result: list[dict[str, Any]] = []
    for topic_id, speaker_id in key_order:
        summaries = groups[(topic_id, speaker_id)]
        result.append(
            {
                "topic_id": topic_id,
                "speaker_id_in_transcript": speaker_id,
                "summary": " ".join(summaries) if summaries else "",
            }
        )
    return result


def _truncate_to_tokens(
    text: str, max_tokens: int, token_counter: Callable[[str], int] | None = None
) -> str:
    """Truncate text to approximately max_tokens (by line to avoid mid-word cut)."""
    from debate_analyzer.analysis.chunking import estimate_tokens

    count = token_counter or estimate_tokens
    if count(text) <= max_tokens:
        return text
    lines = text.split("\n")
    acc: list[str] = []
    n = 0
    for line in lines:
        n += count(line) + 1
        if n > max_tokens:
            break
        acc.append(line)
    return "\n".join(acc)


def run_analysis(
    payload: dict[str, Any],
    generate_batch: Callable[[list[str], int], list[str]],
    max_context_tokens: int = DEFAULT_MAX_CHUNK_TOKENS,
    max_excerpt_tokens: int | None = None,
    token_counter: Callable[[str], int] | None = None,
    max_tokens_per_reply: int = 2048,
    log_progress: Callable[[str], None] | None = None,
    log_llm_call: Callable[[str, str, str], None] | None = None,
) -> dict[str, Any]:
    """
    Run the two-phase LLM analysis on a transcript payload using batched inference.

    Phase 1: extract main topics from the full transcript (in chunks). Phase 2: for
    each topic, one call returns both topic summary and speaker contributions (hybrid).
    Result shape is unchanged: main_topics, topic_summaries, speaker_contributions.

    Args:
        payload: Transcript dict with "transcription" list of segments.
        generate_batch: Backend function (prompts, max_tokens) -> list of model outputs.
        max_context_tokens: Max tokens per chunk for Phase 1; also for excerpt in
            Phase 2 when max_excerpt_tokens is not set. Match model context
            (e.g. LLM_MAX_MODEL_LEN minus reserve).
        max_excerpt_tokens: Optional. When set, Phase 2 excerpts are capped.
        token_counter: Optional token counter; if None, uses character-based estimate.
        max_tokens_per_reply: Max tokens to request from the model per call.
        log_progress: Optional callback for progress (e.g. [LLM]-prefixed stderr).
        log_llm_call: Optional (label, prompt, response) for each LLM call; truncation
            is typically applied by the caller.

    Returns:
        Dict with main_topics, topic_summaries, speaker_contributions for DB storage.
    """
    from debate_analyzer.analysis.chunking import estimate_tokens

    transcription = payload.get("transcription") or []
    flat, line_to_segment = flatten_transcription_with_indices(transcription)
    if not flat.strip():
        return LLMAnalysisResult(
            main_topics=[],
            topic_summaries=[],
            speaker_contributions=[],
        ).to_dict()

    count = token_counter or estimate_tokens
    excerpt_max = (
        max_excerpt_tokens if max_excerpt_tokens is not None else max_context_tokens
    )

    # Phase 1: topics (batched)
    chunks = split_into_chunks(flat, max_tokens=max_context_tokens, token_counter=count)
    if log_progress:
        log_progress(f"Phase 1: Extracting topics ({len(chunks)} chunks).")
    phase1_prompts = [build_topics_chunk_prompt(chunk) for chunk in chunks]
    phase1_responses = generate_batch(phase1_prompts, max_tokens_per_reply)
    if log_llm_call and phase1_prompts:
        p0 = phase1_prompts[0]
        log_llm_call(
            f"Phase 1 batch ({len(phase1_prompts)} chunks)",
            p0[:200] + "..." if len(p0) > 200 else p0,
            f"<{len(phase1_responses)} responses>",
        )
    all_topic_dicts: list[dict[str, Any]] = []
    for out in phase1_responses:
        parsed = _extract_json(out)
        if isinstance(parsed, dict) and "main_topics" in parsed:
            all_topic_dicts.extend(parsed["main_topics"])

    main_topics = _merge_topic_ids(all_topic_dicts)
    for topic in main_topics:
        topic["keywords"] = topic_keywords(
            topic.get("title") or "", topic.get("description") or ""
        )
    if log_progress:
        log_progress(f"Phase 1 done: {len(main_topics)} topics.")
    if not main_topics:
        return LLMAnalysisResult(
            main_topics=[],
            topic_summaries=[],
            speaker_contributions=[],
        ).to_dict()

    # Phase 2: summary and speaker contributions per topic (hybrid, one call per topic)
    if log_progress:
        log_progress(
            f"Phase 2: Summary and speaker contributions for {len(main_topics)} topics."
        )
    phase2_prompts: list[str] = []
    topic_line_ranges: list[tuple[int, int]] = []
    for idx, topic in enumerate(main_topics):
        topic_id = topic.get("id", "")
        title = topic.get("title") or ""
        desc = topic.get("description") or ""
        excerpt, start_line, end_line = get_topic_relevant_excerpt_with_range(
            flat,
            title,
            desc,
            excerpt_max,
            token_counter=count,
            fallback_offset_index=idx,
        )
        topic_line_ranges.append((start_line, end_line))
        phase2_prompts.append(
            build_topic_summary_and_contributions_prompt(topic_id, title, desc, excerpt)
        )
    phase2_responses = generate_batch(phase2_prompts, max_tokens_per_reply)
    if log_llm_call and phase2_prompts:
        p0 = phase2_prompts[0]
        log_llm_call(
            f"Phase 2 batch ({len(phase2_prompts)} topics)",
            p0[:200] + "..." if len(p0) > 200 else p0,
            f"<{len(phase2_responses)} responses>",
        )
    topic_summaries: list[dict[str, Any]] = []
    speaker_contributions: list[dict[str, Any]] = []
    for topic, out in zip(main_topics, phase2_responses):
        topic_id = topic.get("id", "")
        parsed = _extract_json(out)
        if not isinstance(parsed, dict):
            if log_progress:
                log_progress(f"Phase 2: could not parse response for topic {topic_id}.")
            continue
        summary = parsed.get("summary")
        if "topic_id" in parsed and summary is not None:
            topic_summaries.append(
                {
                    "topic_id": str(parsed["topic_id"]),
                    "summary": str(summary),
                }
            )
        for sc in parsed.get("speaker_contributions") or []:
            if isinstance(sc, dict) and str(sc.get("topic_id", "")).strip() == topic_id:
                speaker_contributions.append(
                    {
                        "topic_id": str(sc.get("topic_id", "")),
                        "speaker_id_in_transcript": str(
                            sc.get("speaker_id_in_transcript", "")
                        ),
                        "summary": str(sc.get("summary", "")),
                    }
                )

    speaker_contributions = _aggregate_speaker_contributions(speaker_contributions)

    # Attach start_sec / end_sec to each topic for video linking
    for topic, (start_line, end_line) in zip(main_topics, topic_line_ranges):
        if (
            end_line < start_line
            or not line_to_segment
            or start_line >= len(line_to_segment)
        ):
            topic["start_sec"] = None
            topic["end_sec"] = None
            continue
        seg_start_idx = line_to_segment[start_line]
        seg_end_idx = line_to_segment[min(end_line, len(line_to_segment) - 1)]
        if seg_start_idx >= len(transcription) or seg_end_idx >= len(transcription):
            topic["start_sec"] = None
            topic["end_sec"] = None
            continue
        seg_start = transcription[seg_start_idx]
        seg_end = transcription[seg_end_idx]
        topic["start_sec"] = seg_start.get("start")
        topic["end_sec"] = seg_end.get("end")

    return LLMAnalysisResult(
        main_topics=main_topics,
        topic_summaries=topic_summaries,
        speaker_contributions=speaker_contributions,
    ).to_dict()
