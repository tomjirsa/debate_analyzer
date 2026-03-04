"""Chunk transcript text for LLM context limits."""

from __future__ import annotations

import os
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
    flat, _ = flatten_transcription_with_indices(transcription)
    return flat


def flatten_transcription_with_indices(
    transcription: list[dict[str, Any]],
) -> tuple[str, list[int]]:
    """
    Convert transcript segments to flattened text and map line index to segment index.

    Only segments with non-empty text get a line. line_to_segment[i] is the
    segment index (in transcription) for line i in the flattened string.

    Args:
        transcription: List of segment dicts with "speaker" and "text" keys.

    Returns:
        Tuple of (flat_string, line_to_segment). line_to_segment has length
        equal to the number of lines in flat_string.
    """
    lines: list[str] = []
    line_to_segment: list[int] = []
    for idx, seg in enumerate(transcription):
        speaker = seg.get("speaker") or "SPEAKER_UNKNOWN"
        text = (seg.get("text") or "").strip()
        if text:
            lines.append(f"{speaker}: {text}")
            line_to_segment.append(idx)
    return "\n".join(lines), line_to_segment


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from character count (rough for Czech/European).

    Uses LLM_CHARS_PER_TOKEN (default 4) chars per token when no tokenizer is
    available. Use 3 for safer sizing with Ollama/Czech (fewer chars per chunk).
    """
    raw = os.environ.get("LLM_CHARS_PER_TOKEN", "4").strip()
    try:
        chars_per_token = int(raw)
    except ValueError:
        chars_per_token = 4
    chars_per_token = max(2, min(6, chars_per_token))
    return max(1, len(text) // chars_per_token)


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


def topic_keywords(title: str, description: str) -> list[str]:
    """Return keywords derived from the topic (same as used for excerpt matching).

    Useful for inspection and debugging. Result is sorted for stable output.
    """
    return sorted(_topic_keywords(title, description))


def _line_matches_topic(line: str, keywords: set[str]) -> bool:
    """True if any keyword matches a word (prefix match for Czech morphology).

    Uses word-level prefix matching so e.g. 'rozpočet' matches 'rozpočtu',
    'cyklosteska' matches 'cyklostezka'. Avoids needing a stemmer.
    """
    if not keywords:
        return False
    line_lower = line.lower()
    line_words = set(re.findall(r"[a-z0-9áéíóúýčďěňřšťůž]+", line_lower))
    for kw in keywords:
        for w in line_words:
            if min(len(w), len(kw)) < 2:
                continue
            if w.startswith(kw) or kw.startswith(w):
                return True
    return False


def get_topic_relevant_excerpt(
    flat_transcript: str,
    topic_title: str,
    topic_description: str,
    max_tokens: int,
    token_counter: Callable[[str], int] | None = None,
    window_lines: int = DEFAULT_EXCERPT_WINDOW_LINES,
    fallback_offset_index: int | None = None,
) -> str:
    """
    Build an excerpt of the transcript that is likely to contain the given topic.

    Finds lines where any keyword from the topic title/description appears
    (prefix match for Czech morphology), expands a window around those lines,
    then truncates to max_tokens. If no keyword matches, returns a fallback:
    when fallback_offset_index is not None, a staggered slice from that offset;
    otherwise the first max_tokens of the transcript.

    Args:
        flat_transcript: Flattened transcript (one "SPEAKER_XX: text" per line).
        topic_title: Topic title.
        topic_description: Optional topic description.
        max_tokens: Maximum tokens for the excerpt.
        token_counter: Function that returns token count; if None, uses estimate_tokens.
        window_lines: Lines to include before/after each matching line; also used
            for staggered fallback step when fallback_offset_index is set.
        fallback_offset_index: When no keyword match, start excerpt at this index
            times window_lines (so different topics get different fallback slices).
            None keeps legacy behavior (first max_tokens of transcript).

    Returns:
        Excerpt string (truncated to max_tokens).
    """
    excerpt, _, _ = get_topic_relevant_excerpt_with_range(
        flat_transcript,
        topic_title,
        topic_description,
        max_tokens,
        token_counter=token_counter,
        window_lines=window_lines,
        fallback_offset_index=fallback_offset_index,
    )
    return excerpt


def get_topic_relevant_excerpt_with_range(
    flat_transcript: str,
    topic_title: str,
    topic_description: str,
    max_tokens: int,
    token_counter: Callable[[str], int] | None = None,
    window_lines: int = DEFAULT_EXCERPT_WINDOW_LINES,
    fallback_offset_index: int | None = None,
) -> tuple[str, int, int]:
    """
    Build a topic-relevant excerpt and return its line range in the flat transcript.

    Same logic as get_topic_relevant_excerpt, but also returns start and end
    line indices (0-based, end inclusive) that form the excerpt after truncation.
    Used to map topic conversation to segment timestamps (start_sec, end_sec).

    Args:
        flat_transcript: Flattened transcript (one "SPEAKER_XX: text" per line).
        topic_title: Topic title.
        topic_description: Optional topic description.
        max_tokens: Maximum tokens for the excerpt.
        token_counter: Function that returns token count; if None, uses estimate_tokens.
        window_lines: Lines to include before/after each matching line.
        fallback_offset_index: When no keyword match, staggered slice offset.

    Returns:
        Tuple (excerpt_str, start_line_idx, end_line_idx_inclusive). If no lines,
        returns ("", 0, -1); runner should treat end < start as no range.
    """
    count = token_counter or estimate_tokens
    lines = flat_transcript.split("\n")
    n_lines = len(lines)
    if not lines or max_tokens <= 0:
        out = truncate_to_tokens(flat_transcript, max_tokens, token_counter=count)
        num_kept = len(out.split("\n")) if out else 0
        end_inclusive = num_kept - 1 if num_kept else -1
        return (out, 0, end_inclusive)

    keywords = _topic_keywords(topic_title, topic_description)
    if not keywords:
        out = truncate_to_tokens(flat_transcript, max_tokens, token_counter=count)
        num_kept = len(out.split("\n")) if out else 0
        end_inclusive = num_kept - 1 if num_kept else -1
        return (out, 0, end_inclusive)

    matching_indices: list[int] = []
    for i, line in enumerate(lines):
        if _line_matches_topic(line, keywords):
            matching_indices.append(i)

    if not matching_indices:
        if fallback_offset_index is not None:
            start_line = min(
                fallback_offset_index * window_lines,
                max(0, n_lines - 1),
            )
            excerpt_lines = lines[start_line:]
            excerpt = "\n".join(excerpt_lines)
            out = truncate_to_tokens(excerpt, max_tokens, token_counter=count)
            num_kept = len(out.split("\n")) if out else 0
            end_inclusive = (
                min(start_line + num_kept - 1, n_lines - 1)
                if num_kept
                else start_line - 1
            )
            return (out, start_line, end_inclusive)
        out = truncate_to_tokens(flat_transcript, max_tokens, token_counter=count)
        num_kept = len(out.split("\n")) if out else 0
        end_inclusive = num_kept - 1 if num_kept else -1
        return (out, 0, end_inclusive)

    lo = max(0, min(matching_indices) - window_lines)
    hi = min(n_lines, max(matching_indices) + 1 + window_lines)
    excerpt_lines = lines[lo:hi]
    excerpt = "\n".join(excerpt_lines)
    out = truncate_to_tokens(excerpt, max_tokens, token_counter=count)
    num_kept = len(out.split("\n")) if out else 0
    end_inclusive = min(lo + num_kept - 1, hi - 1) if num_kept else lo - 1
    return (out, lo, end_inclusive)
