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


# Segment summary: one segment → short summary + keywords (JSON).
PROMPT_SEGMENT_SUMMARY = (
    "Summarize the following transcript segment in one short paragraph and "
    "extract 3–8 key terms or phrases (keywords). Output only valid JSON with "
    'exactly two keys: "summary" (string) and "keywords" (array of strings). '
    "No other text.\n\n"
    "Segment text:\n"
    "---\n"
    "{text}\n"
    "---"
)

# Merge: partial summaries + keywords → one summary + one keyword list (JSON).
PROMPT_MERGE_SUMMARIES = (
    "The following are partial summaries and keywords from one long speaker "
    "segment. Combine them into a single short summary and a single list of "
    'keywords (no duplicates). Output only valid JSON with exactly two keys: '
    '"summary" (string) and "keywords" (array of strings). No other text.\n\n'
    "Partial summaries:\n"
    "---\n"
    "{partials}\n"
    "---"
)


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
