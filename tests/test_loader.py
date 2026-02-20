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
