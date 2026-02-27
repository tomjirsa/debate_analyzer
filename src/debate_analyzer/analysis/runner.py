"""Orchestrate LLM analysis: chunking, prompts, and result assembly."""

from __future__ import annotations

import json
from typing import Any, Callable

from debate_analyzer.analysis.chunking import (
    DEFAULT_MAX_CHUNK_TOKENS,
    flatten_transcription,
    split_into_chunks,
)
from debate_analyzer.analysis.prompts import (
    build_speaker_contributions_prompt,
    build_topic_summary_prompt,
    build_topics_chunk_prompt,
)
from debate_analyzer.analysis.schema import LLMAnalysisResult


def _extract_json(text: str) -> dict[str, Any] | list[Any] | None:
    """Extract a JSON object or array from model output (may be wrapped in markdown)."""
    text = text.strip()
    # Find first { or [ and matching } or ].
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


def _merge_topic_ids(topic_dicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate topics by title (case-insensitive); assign stable ids t1, t2, ..."""
    seen: dict[str, dict[str, Any]] = {}
    for t in topic_dicts:
        title = (t.get("title") or "").strip().lower()
        if not title:
            continue
        if title not in seen:
            seen[title] = dict(t)
    result = []
    for i, (_, t) in enumerate(sorted(seen.items(), key=lambda x: x[0]), start=1):
        t["id"] = f"t{i}"
        result.append(t)
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
    generate: Callable[[str, int], str],
    max_context_tokens: int = DEFAULT_MAX_CHUNK_TOKENS,
    token_counter: Callable[[str], int] | None = None,
    max_tokens_per_reply: int = 2048,
    log_progress: Callable[[str], None] | None = None,
    log_llm_call: Callable[[str, str, str], None] | None = None,
) -> dict[str, Any]:
    """
    Run the three-phase LLM analysis on a transcript payload.

    Args:
        payload: Transcript dict with "transcription" list of segments.
        generate: Backend function (prompt, max_tokens) -> model output text.
        max_context_tokens: Max tokens per chunk for Phase 1; also for excerpt in 2/3.
        token_counter: Optional token counter; if None, uses character-based estimate.
        max_tokens_per_reply: Max tokens to request from the model per call.
        log_progress: Optional callback for progress messages (e.g. [LLM]-prefixed stderr).
        log_llm_call: Optional callback (label, prompt, response) for each LLM call; for
            debugging/observability. May contain transcript content; truncation is typically
            applied by the caller.

    Returns:
        Dict with main_topics, topic_summaries, speaker_contributions for DB storage.
    """
    from debate_analyzer.analysis.chunking import estimate_tokens

    transcription = payload.get("transcription") or []
    flat = flatten_transcription(transcription)
    if not flat.strip():
        return LLMAnalysisResult(
            main_topics=[],
            topic_summaries=[],
            speaker_contributions=[],
        ).to_dict()

    count = token_counter or estimate_tokens

    # Phase 1: topics (chunked if needed)
    chunks = split_into_chunks(flat, max_tokens=max_context_tokens, token_counter=count)
    if log_progress:
        log_progress(f"Phase 1: Extracting topics ({len(chunks)} chunks).")
    all_topic_dicts: list[dict[str, Any]] = []
    num_chunks = len(chunks)
    for i, chunk in enumerate(chunks):
        if log_progress:
            log_progress(f"Phase 1: Processing chunk {i + 1}/{num_chunks}.")
        prompt = build_topics_chunk_prompt(chunk)
        out = generate(prompt, max_tokens=max_tokens_per_reply)
        if log_llm_call:
            log_llm_call(f"Phase 1 chunk {i + 1}/{num_chunks}", prompt, out)
        parsed = _extract_json(out)
        if isinstance(parsed, dict) and "main_topics" in parsed:
            all_topic_dicts.extend(parsed["main_topics"])

    main_topics = _merge_topic_ids(all_topic_dicts)
    if log_progress:
        log_progress(f"Phase 1 done: {len(main_topics)} topics.")
    if not main_topics:
        return LLMAnalysisResult(
            main_topics=[],
            topic_summaries=[],
            speaker_contributions=[],
        ).to_dict()

    # Excerpt for Phase 2 and 3: full text truncated to max_context_tokens
    excerpt = _truncate_to_tokens(flat, max_context_tokens, token_counter=count)

    topic_summaries: list[dict[str, Any]] = []
    speaker_contributions: list[dict[str, Any]] = []

    for i, topic in enumerate(main_topics):
        topic_id = topic.get("id", "")
        title = topic.get("title") or ""
        desc = topic.get("description") or ""
        if log_progress:
            log_progress(f"Phase 2/3: Topic {i + 1}/{len(main_topics)}: {title}")

        # Phase 2: topic summary
        prompt2 = build_topic_summary_prompt(topic_id, title, desc, excerpt)
        if log_progress:
            log_progress(f"Phase 2: Generating summary for topic {topic_id}.")
        out2 = generate(prompt2, max_tokens=max_tokens_per_reply)
        if log_llm_call:
            log_llm_call(f"Phase 2 topic {topic_id}", prompt2, out2)
        parsed2 = _extract_json(out2)
        if isinstance(parsed2, dict) and "topic_id" in parsed2 and "summary" in parsed2:
            topic_summaries.append(
                {
                    "topic_id": str(parsed2["topic_id"]),
                    "summary": str(parsed2["summary"]),
                }
            )

        # Phase 3: speaker contributions for this topic
        prompt3 = build_speaker_contributions_prompt(topic_id, title, excerpt)
        if log_progress:
            log_progress(
                f"Phase 3: Generating speaker contributions for topic {topic_id}."
            )
        out3 = generate(prompt3, max_tokens=max_tokens_per_reply)
        if log_llm_call:
            log_llm_call(f"Phase 3 topic {topic_id}", prompt3, out3)
        parsed3 = _extract_json(out3)
        if isinstance(parsed3, dict) and "speaker_contributions" in parsed3:
            for sc in parsed3["speaker_contributions"]:
                if isinstance(sc, dict) and sc.get("topic_id") == topic_id:
                    speaker_contributions.append(
                        {
                            "topic_id": str(sc.get("topic_id", "")),
                            "speaker_id_in_transcript": str(
                                sc.get("speaker_id_in_transcript", "")
                            ),
                            "summary": str(sc.get("summary", "")),
                        }
                    )

    return LLMAnalysisResult(
        main_topics=main_topics,
        topic_summaries=topic_summaries,
        speaker_contributions=speaker_contributions,
    ).to_dict()
