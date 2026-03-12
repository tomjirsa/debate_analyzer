"""Tests for transcript post-processing: aggregate consecutive same-speaker segments."""

from __future__ import annotations

import json
from pathlib import Path

from debate_analyzer.analysis.transcript_postprocess import (
    aggregate_consecutive_speakers,
)


def test_aggregate_empty() -> None:
    """Empty segments list yields empty blocks."""
    assert aggregate_consecutive_speakers([]) == []


def test_aggregate_single_segment() -> None:
    """Single segment becomes one block with uid, start, end, text, speaker."""
    segments = [
        {"start": 0.0, "end": 5.0, "text": "Hello.", "speaker": "SPEAKER_00"},
    ]
    blocks = aggregate_consecutive_speakers(segments)
    assert len(blocks) == 1
    b = blocks[0]
    assert b["start"] == 0.0
    assert b["end"] == 5.0
    assert b["text"] == "Hello."
    assert b["speaker"] == "SPEAKER_00"
    assert "uid" in b and len(b["uid"]) > 0


def test_aggregate_two_same_speaker() -> None:
    """Two same-speaker segments become one block; start/end and text aggregated."""
    segments = [
        {"start": 0.0, "end": 2.0, "text": "First part.", "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 5.0, "text": "Second part.", "speaker": "SPEAKER_00"},
    ]
    blocks = aggregate_consecutive_speakers(segments)
    assert len(blocks) == 1
    b = blocks[0]
    assert b["start"] == 0.0
    assert b["end"] == 5.0
    assert b["text"] == "First part. Second part."
    assert b["speaker"] == "SPEAKER_00"
    assert "uid" in b


def test_aggregate_two_different_speakers() -> None:
    """Two segments with different speakers yield two blocks."""
    segments = [
        {"start": 0.0, "end": 1.0, "text": "A.", "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 2.0, "text": "B.", "speaker": "SPEAKER_01"},
    ]
    blocks = aggregate_consecutive_speakers(segments)
    assert len(blocks) == 2
    assert blocks[0]["speaker"] == "SPEAKER_00"
    assert blocks[0]["text"] == "A."
    assert blocks[1]["speaker"] == "SPEAKER_01"
    assert blocks[1]["text"] == "B."
    assert blocks[0]["uid"] != blocks[1]["uid"]


def test_aggregate_three_alternating() -> None:
    """Three segments A, B, A yield three blocks."""
    segments = [
        {"start": 0.0, "end": 1.0, "text": "A1", "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 2.0, "text": "B", "speaker": "SPEAKER_01"},
        {"start": 2.0, "end": 3.0, "text": "A2", "speaker": "SPEAKER_00"},
    ]
    blocks = aggregate_consecutive_speakers(segments)
    assert len(blocks) == 3
    assert blocks[0]["speaker"] == "SPEAKER_00" and blocks[0]["text"] == "A1"
    assert blocks[1]["speaker"] == "SPEAKER_01" and blocks[1]["text"] == "B"
    assert blocks[2]["speaker"] == "SPEAKER_00" and blocks[2]["text"] == "A2"


def test_aggregate_preserves_confidence_when_present() -> None:
    """When segments have confidence, block gets average confidence."""
    segments = [
        {"start": 0.0, "end": 1.0, "text": "A", "speaker": "S", "confidence": 0.8},
        {"start": 1.0, "end": 2.0, "text": "B", "speaker": "S", "confidence": 1.0},
    ]
    blocks = aggregate_consecutive_speakers(segments)
    assert len(blocks) == 1
    assert blocks[0]["confidence"] == 0.9


def test_aggregate_speaker_unknown_normalized() -> None:
    """Missing speaker is normalized to SPEAKER_UNKNOWN; consecutive unknown merge."""
    segments = [
        {"start": 0.0, "end": 1.0, "text": "X", "speaker": None},
        {"start": 1.0, "end": 2.0, "text": "Y", "speaker": ""},
    ]
    blocks = aggregate_consecutive_speakers(segments)
    assert len(blocks) == 1
    assert blocks[0]["speaker"] == "SPEAKER_UNKNOWN"
    assert blocks[0]["text"] == "X Y"


def test_postprocess_job_run_one_local(tmp_path: Path) -> None:
    """Job reads raw, aggregates, writes _transcription.json with blocks (uid)."""
    raw_path = tmp_path / "debate_transcription_raw.json"
    payload = {
        "video_path": "/x",
        "duration": 10.0,
        "transcription": [
            {"start": 0, "end": 1, "text": "First.", "speaker": "SPEAKER_00"},
            {"start": 1, "end": 2, "text": "Second.", "speaker": "SPEAKER_00"},
            {"start": 2, "end": 3, "text": "Other.", "speaker": "SPEAKER_01"},
        ],
    }
    raw_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    from debate_analyzer.batch import transcript_postprocess_job

    n = transcript_postprocess_job.run(str(raw_path))
    assert n == 1
    out_path = tmp_path / "debate_transcription.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    # Three segments, two same-speaker runs -> two blocks
    assert len(data["transcription"]) == 2
    assert data["transcription"][0]["text"] == "First. Second."
    assert data["transcription"][0]["speaker"] == "SPEAKER_00"
    assert data["transcription"][1]["text"] == "Other."
    assert data["transcription"][1]["speaker"] == "SPEAKER_01"
    for block in data["transcription"]:
        assert "uid" in block and len(block["uid"]) > 0
    assert data["video_path"] == "/x"
    assert data["duration"] == 10.0
