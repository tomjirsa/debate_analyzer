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
