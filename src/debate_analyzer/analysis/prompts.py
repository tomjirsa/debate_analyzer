"""Prompt templates for LLM transcript analysis and post-processing."""

from __future__ import annotations

# System-level instruction for response language (injected by backends).
SYSTEM_PROMPT_RESPONSE_LANGUAGE = (
    "Always respond in Czech. Use Czech for all topic labels, descriptions, "
    "summaries, and any text inside JSON."
)

# Transcript post-processing: grammar and ASR errors only; do not change meaning.
PROMPT_CORRECT_SEGMENT = (
    "Correct only grammar and obvious transcription (speech-to-text) errors in the "
    "following Czech text. Do not change meaning, paraphrase, add, remove, or "
    "reinterpret content. Fix only: typos, verb agreement, punctuation, and clear "
    "ASR mishears (e.g. homophones). Output only the corrected text, one segment.\n\n"
    "Text:\n"
    "---\n"
    "{text}\n"
    "---\n"
    "Corrected text:"
)


def build_correct_segment_prompt(text: str) -> str:
    """Build prompt for transcript post-processing (one segment)."""
    return PROMPT_CORRECT_SEGMENT.format(text=text)


# Segment summary: one segment → summary + keywords (JSON).
PROMPT_SEGMENT_SUMMARY = (
    "Read the following transcript segment and write a clear summary in Czech "
    "that captures what was said: main points, positions, arguments, and any "
    "concrete facts or decisions mentioned. Cover the segment content faithfully; "
    "do not invent details not present in the text. "
    "Also extract 3–8 key terms or phrases (keywords). "
    "Output only valid JSON with exactly two keys (ASCII identifiers): "
    '"summary" (string) and "keywords" (array of strings). '
    "Do not use Czech or translated key names (e.g. not shrnutí). "
    "No other text.\n\n"
    "Segment text:\n"
    "---\n"
    "{text}\n"
    "---"
)

# Merge: partial summaries + keywords → one summary + one keyword list (JSON).
# Used for long-segment chunks, per-speaker merges, and transcript-level merge.
PROMPT_MERGE_SUMMARIES = (
    "The following are partial summaries and keywords from related parts of the "
    "transcript (e.g. chunks of one long turn, or multiple turns to combine). "
    "Merge them into one coherent Czech summary of the combined content: "
    "preserve important details, unify overlapping points, and avoid repetition. "
    "Produce a single merged keyword list (no duplicates). "
    "Output only valid JSON with exactly two keys (ASCII identifiers): "
    '"summary" (string) and "keywords" (array of strings). '
    "Do not use Czech key names. No other text.\n\n"
    "Partial summaries:\n"
    "---\n"
    "{partials}\n"
    "---"
)

# Follow-up when the first reply is not parseable or lacks required keys.
PROMPT_JSON_RETRY_PREFIX = (
    "Your previous reply was not usable. Reply with ONLY one JSON object and no "
    "other text (no markdown, no commentary). The object must use exactly these "
    'two keys: "summary" (string, Czech) and "keywords" (array of strings). '
    "Keys must be English identifiers as shown; do not use shrnutí or other labels."
)


def build_json_retry_prompt(original_prompt: str) -> str:
    """Build a single follow-up user message: strict JSON instruction + original ask."""
    return f"{PROMPT_JSON_RETRY_PREFIX}\n\n{original_prompt}"


def build_segment_summary_prompt(text: str) -> str:
    """Build prompt for summarizing one segment (summary + keywords)."""
    return PROMPT_SEGMENT_SUMMARY.format(text=text)


def build_merge_summaries_prompt(
    partial_summaries: list[tuple[str, list[str]]],
) -> str:
    """Build prompt to merge partial (summary, keywords) into one summary + keywords."""
    lines = []
    for i, (summary, keywords) in enumerate(partial_summaries, 1):
        lines.append(f"{i}. Summary: {summary}")
        if keywords:
            lines.append(f"   Keywords: {', '.join(keywords)}")
    return PROMPT_MERGE_SUMMARIES.format(partials="\n\n".join(lines))
