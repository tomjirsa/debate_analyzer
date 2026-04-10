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
    Kept in sync with
    ``agent-skills/segment-prompt-tuning/segment_summary_prompt_draft.txt``.

    Returns:
        Raw template string (before ``str.format``).

    Raises:
        FileNotFoundError: If the template file is missing next to this module.
    """
    path = Path(__file__).resolve().parent / "segment_summary_prompt.txt"
    return path.read_text(encoding="utf-8")


# Segment summary: one segment → summary + keywords (JSON).
PROMPT_SEGMENT_SUMMARY = _load_segment_summary_prompt_template()


def _analysis_dir() -> Path:
    """Directory containing ``segment_summary_prompt.txt`` and merge templates."""
    return Path(__file__).resolve().parent


def _load_merge_template(filename: str) -> str:
    """Load a merge prompt template; must contain ``{partials}`` placeholder.

    Args:
        filename: File name under the analysis package directory.

    Returns:
        Raw template string (before ``str.format``).

    Raises:
        FileNotFoundError: If the template file is missing.
    """
    path = _analysis_dir() / filename
    return path.read_text(encoding="utf-8")


# Merge: partial summaries + keywords → one summary + one keyword list (JSON).
PROMPT_MERGE_SEGMENT_CHUNK = _load_merge_template("merge_segment_chunk_prompt.txt")
PROMPT_MERGE_SPEAKER = _load_merge_template("merge_speaker_prompt.txt")
PROMPT_MERGE_TRANSCRIPT = _load_merge_template("merge_transcript_prompt.txt")

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


def _build_merge_prompt(
    partial_summaries: list[tuple[str, list[str]]],
    template: str,
) -> str:
    return template.format(partials=format_merge_partials_block(partial_summaries))


def build_merge_segment_chunk_prompt(
    partial_summaries: list[tuple[str, list[str]]],
) -> str:
    """Merge chunk partials for one long segment into one summary + keywords."""
    return _build_merge_prompt(partial_summaries, PROMPT_MERGE_SEGMENT_CHUNK)


def build_merge_speaker_prompt(
    partial_summaries: list[tuple[str, list[str]]],
) -> str:
    """Merge one speaker's segment summaries into one contribution + keywords."""
    return _build_merge_prompt(partial_summaries, PROMPT_MERGE_SPEAKER)


def build_merge_transcript_prompt(
    partial_summaries: list[tuple[str, list[str]]],
) -> str:
    """Merge per-speaker summaries into one transcript-level summary + keywords."""
    return _build_merge_prompt(partial_summaries, PROMPT_MERGE_TRANSCRIPT)
