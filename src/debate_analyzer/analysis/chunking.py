"""Chunk transcript text for LLM context limits."""

from __future__ import annotations

import re
from typing import Any, Callable

# Default: reserve space for system prompt and output (~8k tokens).
DEFAULT_MAX_CHUNK_TOKENS = 24_000
DEFAULT_OVERLAP_TOKENS = 500

# Window (lines) around keyword matches when building topic-relevant excerpt
DEFAULT_EXCERPT_WINDOW_LINES = 50


def flatten_transcription(transcription: list[dict[str, Any]]) -> str:
    """
    Convert transcript segments to a single text with "SPEAKER_XX: text" lines.

    Args:
        transcription: List of segment dicts with "speaker" and "text" keys.

    Returns:
        Single string, one "SPEAKER_XX: text" per segment.
    """
    lines: list[str] = []
    for seg in transcription:
        speaker = seg.get("speaker") or "SPEAKER_UNKNOWN"
        text = (seg.get("text") or "").strip()
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from character count (rough for Czech/European).

    Use ~4 chars per token as a safe upper bound when no tokenizer is available.
    """
    return max(1, len(text) // 4)


def split_into_chunks(
    text: str,
    max_tokens: int = DEFAULT_MAX_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    token_counter: Callable[[str], int] | None = None,
) -> list[str]:
    """
    Split text into chunks that each have at most max_tokens
    (by token_counter or estimate).

    Chunks overlap by overlap_tokens to avoid cutting topics at boundaries.
    Splits on newlines where possible to keep speaker turns intact.

    Args:
        text: Full flattened transcript text.
        max_tokens: Maximum tokens per chunk.
        overlap_tokens: Overlap between consecutive chunks.
        token_counter: Function that returns token count for a string.
            If None, uses estimate_tokens.

    Returns:
        List of chunk strings. Single chunk if text fits in max_tokens.
    """
    count = token_counter or estimate_tokens
    total = count(text)
    if total <= max_tokens:
        return [text] if text.strip() else []

    lines = text.split("\n")
    if not lines:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for line in lines:
        line_tokens = count(line) + 1  # +1 for newline
        if current_tokens + line_tokens > max_tokens and current:
            chunk_text = "\n".join(current)
            chunks.append(chunk_text)
            # Start next chunk with overlap: keep lines that fit in overlap_tokens
            overlap_remaining = overlap_tokens
            new_current: list[str] = []
            for i in range(len(current) - 1, -1, -1):
                t = count(current[i]) + 1
                if overlap_remaining >= t:
                    new_current.insert(0, current[i])
                    overlap_remaining -= t
                else:
                    break
            current = new_current
            current_tokens = count(chunk_text) - (overlap_tokens - overlap_remaining)
            if current_tokens < 0:
                current_tokens = sum(count(ln) + 1 for ln in current)
        current.append(line)
        current_tokens += line_tokens
    if current:
        chunks.append("\n".join(current))
    return chunks


def truncate_to_tokens(
    text: str,
    max_tokens: int,
    token_counter: Callable[[str], int] | None = None,
) -> str:
    """
    Truncate text to approximately max_tokens (by line to avoid mid-word cut).

    Args:
        text: Full text.
        max_tokens: Maximum tokens to keep.
        token_counter: Function that returns token count; if None, uses estimate_tokens.

    Returns:
        Truncated text (may be empty if max_tokens <= 0).
    """
    count = token_counter or estimate_tokens
    if max_tokens <= 0:
        return ""
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


def _topic_keywords(title: str, description: str) -> set[str]:
    """Extract meaningful keywords from topic title and description (min length 2)."""
    combined = f"{title or ''} {description or ''}".lower()
    # Allow letters (including Czech), digits
    words = re.findall(r"[a-z0-9áéíóúýčďěňřšťůž]+", combined)
    return {w for w in words if len(w) >= 2}


def get_topic_relevant_excerpt(
    flat_transcript: str,
    topic_title: str,
    topic_description: str,
    max_tokens: int,
    token_counter: Callable[[str], int] | None = None,
    window_lines: int = DEFAULT_EXCERPT_WINDOW_LINES,
) -> str:
    """
    Build an excerpt of the transcript that is likely to contain the given topic.

    Finds lines where any keyword from the topic title/description appears,
    expands a window around those lines, then truncates to max_tokens.
    If no keyword matches, returns the first max_tokens of the transcript.

    Args:
        flat_transcript: Flattened transcript (one "SPEAKER_XX: text" per line).
        topic_title: Topic title.
        topic_description: Optional topic description.
        max_tokens: Maximum tokens for the excerpt.
        token_counter: Function that returns token count; if None, uses estimate_tokens.
        window_lines: Lines to include before/after each matching line.

    Returns:
        Excerpt string (truncated to max_tokens).
    """
    count = token_counter or estimate_tokens
    lines = flat_transcript.split("\n")
    if not lines or max_tokens <= 0:
        return truncate_to_tokens(flat_transcript, max_tokens, token_counter=count)

    keywords = _topic_keywords(topic_title, topic_description)
    if not keywords:
        return truncate_to_tokens(flat_transcript, max_tokens, token_counter=count)

    matching_indices: list[int] = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in keywords):
            matching_indices.append(i)

    if not matching_indices:
        return truncate_to_tokens(flat_transcript, max_tokens, token_counter=count)

    lo = max(0, min(matching_indices) - window_lines)
    hi = min(len(lines), max(matching_indices) + 1 + window_lines)
    excerpt_lines = lines[lo:hi]
    excerpt = "\n".join(excerpt_lines)
    return truncate_to_tokens(excerpt, max_tokens, token_counter=count)
