"""Load transcript JSON and speaker stats parquet from S3 URI or local file path."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import boto3  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]


def load_transcript_payload(source_uri: str) -> dict[str, Any]:
    """
    Load transcript JSON from source_uri.
    - s3://bucket/key -> fetch via boto3.
    - file:///path or /path -> read from filesystem.
    - Otherwise treat as local path.

    Returns:
        Parsed JSON dict (transcription list, duration, etc.).

    Raises:
        FileNotFoundError: Local file does not exist.
        ValueError: Unsupported scheme or invalid JSON.
    """
    source_uri = source_uri.strip()
    if source_uri.startswith("s3://"):
        return _load_from_s3(source_uri)
    if source_uri.startswith("file://"):
        path = Path(source_uri[7:])
    else:
        path = Path(source_uri)
    return _load_from_file(path)


def _load_from_s3(uri: str) -> dict[str, Any]:
    """Parse s3://bucket/key and get object content as JSON."""
    if not uri.startswith("s3://") or len(uri) < 8:
        raise ValueError(f"Invalid S3 URI: {uri}")
    rest = uri[5:]
    parts = rest.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    if not key:
        raise ValueError(f"Invalid S3 key: {uri}")
    client = boto3.client("s3")
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read().decode("utf-8")
    return json.loads(body)


def _load_from_file(path: Path) -> dict[str, Any]:
    """Read JSON from local file."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_speaker_stats_parquet(parquet_uri: str) -> list[dict[str, Any]]:
    """
    Load speaker stats from a parquet file (S3 or local).

    For s3:// URIs, fetches the object and reads with pyarrow. For local paths,
    reads from the filesystem. Returns a list of dicts with keys
    speaker_id_in_transcript, total_seconds, segment_count, word_count.
    On missing file or non-S3/local, returns empty list (no exception).

    Args:
        parquet_uri: S3 URI (s3://bucket/key) or local path to parquet file.

    Returns:
        List of stat dicts, or empty list if unreadable.
    """
    parquet_uri = parquet_uri.strip()
    try:
        if parquet_uri.startswith("s3://"):
            return _load_speaker_stats_from_s3(parquet_uri)
        if parquet_uri.startswith("file://"):
            path = Path(parquet_uri[7:])
        else:
            path = Path(parquet_uri)
        return _load_speaker_stats_from_file(path)
    except Exception:
        return []


def _load_speaker_stats_from_s3(uri: str) -> list[dict[str, Any]]:
    """Fetch parquet from S3 and return list of stat dicts."""
    if not uri.startswith("s3://") or len(uri) < 8:
        return []
    rest = uri[5:]
    parts = rest.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    if not key:
        return []
    client = boto3.client("s3")
    try:
        response = client.get_object(Bucket=bucket, Key=key)
    except Exception:
        return []
    body = response["Body"].read()
    table = pq.read_table(BytesIO(body))
    return _arrow_table_to_stat_rows(table)


def _load_speaker_stats_from_file(path: Path) -> list[dict[str, Any]]:
    """Read parquet from local file and return list of stat dicts."""
    if not path.exists():
        return []
    table = pq.read_table(path)
    return _arrow_table_to_stat_rows(table)


# Optional extended stat columns (parquet may omit them for backward compat).
_OPTIONAL_STAT_COLUMNS = (
    "wpm",
    "avg_segment_duration_sec",
    "shortest_talk_sec",
    "longest_talk_sec",
    "median_segment_duration_sec",
    "turn_count",
    "avg_turn_length_sec",
    "avg_turn_length_segments",
    "is_first_speaker",
    "is_last_speaker",
    "share_speaking_time",
    "share_words",
)


def _arrow_table_to_stat_rows(table: Any) -> list[dict[str, Any]]:
    """Convert pyarrow table to list of stat dicts."""
    if table.num_rows == 0:
        return []
    columns = set(table.column_names)
    required = {
        "speaker_id_in_transcript",
        "total_seconds",
        "segment_count",
        "word_count",
    }
    if not required.issubset(columns):
        return []
    rows: list[dict[str, Any]] = []
    for i in range(table.num_rows):
        row: dict[str, Any] = {
            "speaker_id_in_transcript": table.column("speaker_id_in_transcript")[
                i
            ].as_py(),
            "total_seconds": float(table.column("total_seconds")[i].as_py()),
            "segment_count": int(table.column("segment_count")[i].as_py()),
            "word_count": int(table.column("word_count")[i].as_py()),
        }
        for col in _OPTIONAL_STAT_COLUMNS:
            if col not in columns:
                row[col] = None
                continue
            val = table.column(col)[i]
            if val is None or (hasattr(val, "as_py") and val.as_py() is None):
                row[col] = None
                continue
            py_val = val.as_py() if hasattr(val, "as_py") else val
            if col in ("is_first_speaker", "is_last_speaker"):
                row[col] = bool(py_val)
            elif col == "turn_count":
                row[col] = int(py_val) if py_val is not None else None
            else:
                row[col] = float(py_val) if py_val is not None else None
        rows.append(row)
    return rows
