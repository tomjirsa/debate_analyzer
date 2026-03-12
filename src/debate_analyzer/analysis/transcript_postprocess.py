"""Aggregate consecutive same-speaker transcript segments into blocks."""

from __future__ import annotations

import uuid
from typing import Any


def aggregate_consecutive_speakers(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge consecutive segments with the same speaker into one block per run.

    Each block has aggregated start (min), end (max), concatenated text,
    speaker, and a new uid. Segments with missing speaker are normalized to
    SPEAKER_UNKNOWN so they merge with other unknown segments.

    Args:
        segments: Ordered list of segment dicts with "start", "end", "text",
            "speaker", and optionally "confidence". Segments without start/end
            are included in the run but not in min/max (only segments with
            both numeric start and end contribute to block start/end).

    Returns:
        List of block dicts: start, end, text, speaker, uid; optionally
        confidence (average of merged segments when present).
    """
    if not segments:
        return []

    blocks: list[dict[str, Any]] = []
    current_speaker = segments[0].get("speaker") or "SPEAKER_UNKNOWN"
    current_texts: list[str] = []
    current_starts: list[float] = []
    current_ends: list[float] = []
    current_confidences: list[float] = []

    def flush_block() -> None:
        if not current_texts and not current_starts and not current_ends:
            return
        text = " ".join((t or "").strip() for t in current_texts).strip()
        start = min(current_starts) if current_starts else 0.0
        end = max(current_ends) if current_ends else 0.0
        conf = (
            sum(current_confidences) / len(current_confidences)
            if current_confidences
            else None
        )
        block: dict[str, Any] = {
            "start": start,
            "end": end,
            "text": text,
            "speaker": current_speaker,
            "uid": str(uuid.uuid4()),
        }
        if conf is not None:
            block["confidence"] = conf
        blocks.append(block)

    for seg in segments:
        speaker = seg.get("speaker") or "SPEAKER_UNKNOWN"
        start = seg.get("start")
        end = seg.get("end")
        text = seg.get("text") or ""
        confidence = seg.get("confidence")

        if speaker != current_speaker:
            flush_block()
            current_speaker = speaker
            current_texts = []
            current_starts = []
            current_ends = []
            current_confidences = []

        current_texts.append(text)
        if start is not None and end is not None:
            try:
                current_starts.append(float(start))
                current_ends.append(float(end))
            except (TypeError, ValueError):
                pass
        if confidence is not None:
            try:
                current_confidences.append(float(confidence))
            except (TypeError, ValueError):
                pass

    flush_block()
    return blocks
