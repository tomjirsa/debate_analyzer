"""Tests for the batch stats job (per-speaker stats computation)."""

import json
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]
from debate_analyzer.batch.stats_job import _compute_speaker_stats, _run_local, run


def test_compute_speaker_stats_empty():
    """Empty transcription yields empty list."""
    assert _compute_speaker_stats([]) == []


def test_compute_speaker_stats_single_speaker():
    """Single speaker aggregates total_seconds, segment_count, word_count."""
    transcription = [
        {"start": 0, "end": 3, "text": "one two three", "speaker": "SPEAKER_00"},
        {"start": 3, "end": 6, "text": "four five", "speaker": "SPEAKER_00"},
    ]
    rows = _compute_speaker_stats(transcription)
    assert len(rows) == 1
    assert rows[0]["speaker_id_in_transcript"] == "SPEAKER_00"
    assert rows[0]["total_seconds"] == 6.0
    assert rows[0]["segment_count"] == 2
    assert rows[0]["word_count"] == 5


def test_compute_speaker_stats_two_speakers():
    """Two speakers get separate rows with extended stats."""
    transcription = [
        {"start": 0, "end": 2, "text": "hi", "speaker": "SPEAKER_00"},
        {"start": 2, "end": 5, "text": "hello world", "speaker": "SPEAKER_01"},
    ]
    rows = _compute_speaker_stats(transcription, transcript_duration=5.0)
    assert len(rows) == 2
    by_speaker = {r["speaker_id_in_transcript"]: r for r in rows}
    assert by_speaker["SPEAKER_00"]["total_seconds"] == 2.0
    assert by_speaker["SPEAKER_00"]["word_count"] == 1
    assert by_speaker["SPEAKER_00"]["turn_count"] == 1
    assert by_speaker["SPEAKER_00"]["is_first_speaker"] is True
    assert by_speaker["SPEAKER_00"]["is_last_speaker"] is False
    assert by_speaker["SPEAKER_00"]["share_speaking_time"] == 2.0 / 5.0
    assert by_speaker["SPEAKER_00"]["share_words"] == 1 / 3  # 1 word of 3
    assert by_speaker["SPEAKER_01"]["total_seconds"] == 3.0
    assert by_speaker["SPEAKER_01"]["word_count"] == 2
    assert by_speaker["SPEAKER_01"]["is_first_speaker"] is False
    assert by_speaker["SPEAKER_01"]["is_last_speaker"] is True
    assert by_speaker["SPEAKER_01"]["wpm"] == 40.0  # 2 words / (3/60) min


def test_compute_speaker_stats_missing_speaker_uses_unknown():
    """Segment without speaker key is treated as SPEAKER_UNKNOWN."""
    transcription = [{"start": 0, "end": 1, "text": "x", "speaker": None}]
    rows = _compute_speaker_stats(transcription)
    assert len(rows) == 1
    assert rows[0]["speaker_id_in_transcript"] == "SPEAKER_UNKNOWN"


def test_run_local_writes_parquet(tmp_path: Path) -> None:
    """Local run reads transcript JSONs and writes parquet with extended columns."""
    payload = {
        "duration": 5.0,
        "transcription": [
            {"start": 0, "end": 2, "text": "hi", "speaker": "SPEAKER_00"},
            {"start": 2, "end": 5, "text": "hello world", "speaker": "SPEAKER_01"},
        ],
    }
    (tmp_path / "debate_transcription.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    n = _run_local(tmp_path)
    assert n == 1
    parquet_path = tmp_path / "debate_speaker_stats.parquet"
    assert parquet_path.exists()
    table = pq.read_table(parquet_path)
    assert table.num_rows == 2
    assert "speaker_id_in_transcript" in table.column_names
    assert "total_seconds" in table.column_names
    assert "wpm" in table.column_names
    assert "turn_count" in table.column_names
    assert "share_speaking_time" in table.column_names


def test_compute_speaker_stats_multiple_turns():
    """Turn count and shortest/longest talk reflect contiguous runs."""
    transcription = [
        {"start": 0, "end": 1, "text": "a", "speaker": "SPEAKER_00"},
        {"start": 1, "end": 3, "text": "b c", "speaker": "SPEAKER_00"},
        {"start": 3, "end": 4, "text": "d", "speaker": "SPEAKER_01"},
        {"start": 4, "end": 10, "text": "e f g h", "speaker": "SPEAKER_00"},
    ]
    rows = _compute_speaker_stats(transcription)
    by_speaker = {r["speaker_id_in_transcript"]: r for r in rows}
    assert by_speaker["SPEAKER_00"]["turn_count"] == 2
    assert by_speaker["SPEAKER_00"]["shortest_talk_sec"] == 3.0  # first turn 1+2 sec
    assert by_speaker["SPEAKER_00"]["longest_talk_sec"] == 6.0  # second turn 6 sec
    assert by_speaker["SPEAKER_01"]["turn_count"] == 1
    assert by_speaker["SPEAKER_01"]["shortest_talk_sec"] == 1.0
    assert by_speaker["SPEAKER_01"]["longest_talk_sec"] == 1.0


def test_compute_speaker_stats_no_duration_share_speaking_time_none():
    """Without transcript_duration, share_speaking_time is None."""
    transcription = [{"start": 0, "end": 1, "text": "x", "speaker": "S0"}]
    rows = _compute_speaker_stats(transcription)
    assert len(rows) == 1
    assert rows[0]["share_speaking_time"] is None
    assert rows[0]["share_words"] == 1.0


def test_run_dispatches_to_local_for_file_uri(tmp_path: Path) -> None:
    """run() with file:// prefix uses local path."""
    payload = {"transcription": [{"start": 0, "end": 1, "text": "x", "speaker": "S0"}]}
    (tmp_path / "clip_transcription.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    n = run(f"file://{tmp_path}")
    assert n == 1
    assert (tmp_path / "clip_speaker_stats.parquet").exists()
