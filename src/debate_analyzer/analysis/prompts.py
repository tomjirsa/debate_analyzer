"""Prompt templates for LLM transcript analysis and post-processing."""

from __future__ import annotations

from pathlib import Path

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


def _load_segment_summary_prompt_template() -> str:
    """Load segment-summary prompt template from ``segment_summary_prompt.txt``.

    The template must contain a single ``{text}`` placeholder for the segment body.
    Kept in sync with ``agent-skills/segment-prompt-tuning/segment_summary_prompt_draft.txt``.

    Returns:
        Raw template string (before ``str.format``).

    Raises:
        FileNotFoundError: If the template file is missing next to this module.
    """
    path = Path(__file__).resolve().parent / "segment_summary_prompt.txt"
    return path.read_text(encoding="utf-8")


# Segment summary: one segment → summary + keywords (JSON).
PROMPT_SEGMENT_SUMMARY = _load_segment_summary_prompt_template()


def _load_merge_summaries_prompt_template() -> str:
    """Load merge prompt template from ``merge_summaries_prompt.txt``.

    The template must contain a single ``{partials}`` placeholder for the
    formatted partial-summary block. Kept in sync with
    ``agent-skills/segment-prompt-tuning/merge_summaries_prompt_draft.txt``.

    Returns:
        Raw template string (before ``str.format``).

    Raises:
        FileNotFoundError: If the template file is missing next to this module.
    """
    path = Path(__file__).resolve().parent / "merge_summaries_prompt.txt"
    return path.read_text(encoding="utf-8")


# Merge: partial summaries + keywords → one summary + one keyword list (JSON).
# Used for long-segment chunks, per-speaker merges, and transcript-level merge.
PROMPT_MERGE_SUMMARIES = _load_merge_summaries_prompt_template()

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


def format_merge_partials_block(
    partial_summaries: list[tuple[str, list[str]]],
) -> str:
    """Format partial (summary, keywords) tuples for the merge prompt body."""
    lines: list[str] = []
    for i, (summary, keywords) in enumerate(partial_summaries, 1):
        lines.append(f"{i}. Summary: {summary}")
        if keywords:
            lines.append(f"   Keywords: {', '.join(keywords)}")
    return "\n\n".join(lines)


def build_merge_summaries_prompt(
    partial_summaries: list[tuple[str, list[str]]],
) -> str:
    """Build prompt to merge partial (summary, keywords) into one summary + keywords."""
    return PROMPT_MERGE_SUMMARIES.format(
        partials=format_merge_partials_block(partial_summaries),
    )
