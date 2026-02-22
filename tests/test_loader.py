"""Tests for loader module (transcript JSON and speaker stats parquet)."""

import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from debate_analyzer.api.loader import load_speaker_stats_parquet


def test_load_speaker_stats_parquet_local_file():
    """Loading from a local parquet file returns the expected rows."""
    rows = [
        {
            "speaker_id_in_transcript": "SPEAKER_00",
            "total_seconds": 10.0,
            "segment_count": 2,
            "word_count": 5,
        },
        {
            "speaker_id_in_transcript": "SPEAKER_01",
            "total_seconds": 5.0,
            "segment_count": 1,
            "word_count": 2,
        },
    ]
    table = pa.table(
        {
            "speaker_id_in_transcript": [r["speaker_id_in_transcript"] for r in rows],
            "total_seconds": pa.array(
                [r["total_seconds"] for r in rows], type=pa.float64()
            ),
            "segment_count": pa.array(
                [r["segment_count"] for r in rows], type=pa.int64()
            ),
            "word_count": pa.array([r["word_count"] for r in rows], type=pa.int64()),
        }
    )
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        pq.write_table(table, f.name)
    try:
        result = load_speaker_stats_parquet(f.name)
        assert len(result) == 2
        assert result[0]["speaker_id_in_transcript"] == "SPEAKER_00"
        assert result[0]["total_seconds"] == 10.0
        assert result[1]["word_count"] == 2
    finally:
        Path(f.name).unlink(missing_ok=True)


def test_load_speaker_stats_parquet_missing_file_returns_empty():
    """Non-existent local path returns empty list."""
    result = load_speaker_stats_parquet("/nonexistent/path.parquet")
    assert result == []


def test_load_speaker_stats_parquet_invalid_s3_returns_empty():
    """Invalid or non-S3 URI returns empty list (no exception)."""
    result = load_speaker_stats_parquet("not-s3://bucket/key")
    assert result == []


def test_load_speaker_stats_parquet_old_columns_only():
    """Parquet with only legacy columns loads; optional extended keys are None."""
    table = pa.table(
        {
            "speaker_id_in_transcript": ["SPEAKER_00"],
            "total_seconds": pa.array([10.0], type=pa.float64()),
            "segment_count": pa.array([2], type=pa.int64()),
            "word_count": pa.array([5], type=pa.int64()),
        }
    )
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        pq.write_table(table, f.name)
    try:
        result = load_speaker_stats_parquet(f.name)
        assert len(result) == 1
        assert result[0]["total_seconds"] == 10.0
        assert result[0].get("wpm") is None
        assert result[0].get("turn_count") is None
    finally:
        Path(f.name).unlink(missing_ok=True)


def test_load_speaker_stats_parquet_with_extended_columns():
    """Parquet with extended columns loads and returns all keys."""
    table = pa.table(
        {
            "speaker_id_in_transcript": ["SPEAKER_00"],
            "total_seconds": pa.array([60.0], type=pa.float64()),
            "segment_count": pa.array([3], type=pa.int64()),
            "word_count": pa.array([120], type=pa.int64()),
            "wpm": pa.array([120.0], type=pa.float64()),
            "turn_count": pa.array([2], type=pa.int64()),
            "is_first_speaker": pa.array([True], type=pa.bool_()),
            "share_words": pa.array([0.5], type=pa.float64()),
        }
    )
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        pq.write_table(table, f.name)
    try:
        result = load_speaker_stats_parquet(f.name)
        assert len(result) == 1
        assert result[0]["wpm"] == 120.0
        assert result[0]["turn_count"] == 2
        assert result[0]["is_first_speaker"] is True
        assert result[0]["share_words"] == 0.5
    finally:
        Path(f.name).unlink(missing_ok=True)
