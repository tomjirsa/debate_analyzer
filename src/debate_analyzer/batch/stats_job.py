"""
Compute per-speaker statistics per transcript and write to parquet.

Reads TRANSCRIPTS_S3_PREFIX (or TRANSCRIPTS_PREFIX) from the environment:
- If value is an s3:// URI: lists *_transcription.json in S3, writes
  <stem>_speaker_stats.parquet to the same S3 prefix (AWS Batch).
- If value is a local path or file:// URI: lists *_transcription.json in that
  directory, writes <stem>_speaker_stats.parquet to the same directory (local dev).

Invoked by the stats Batch job entrypoint
(e.g. python -m debate_analyzer.batch.stats_job).
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any

import boto3  # type: ignore[import-untyped]
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    """Return (bucket, key) for an s3:// URI."""
    if not uri.startswith("s3://") or len(uri) < 8:
        raise ValueError(f"Invalid S3 URI: {uri}")
    rest = uri[5:]
    parts = rest.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    return bucket, key


def _compute_speaker_stats(transcription: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Aggregate per-speaker stats from transcript segments.

    Args:
        transcription: List of segment dicts with start, end, text, speaker.

    Returns:
        List of dicts with speaker_id_in_transcript, total_seconds,
        segment_count, word_count.
    """
    by_speaker: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total_seconds": 0.0, "segment_count": 0, "word_count": 0}
    )
    for seg in transcription:
        speaker = seg.get("speaker") or "SPEAKER_UNKNOWN"
        start = seg.get("start")
        end = seg.get("end")
        text = seg.get("text") or ""
        if start is not None and end is not None:
            by_speaker[speaker]["total_seconds"] += float(end) - float(start)
        by_speaker[speaker]["segment_count"] += 1
        by_speaker[speaker]["word_count"] += len(text.split())
    return [
        {
            "speaker_id_in_transcript": speaker,
            "total_seconds": data["total_seconds"],
            "segment_count": data["segment_count"],
            "word_count": data["word_count"],
        }
        for speaker, data in sorted(by_speaker.items())
    ]


def _rows_to_parquet_table(rows: list[dict[str, Any]]) -> pa.Table:
    """Build a pyarrow table from stat rows (shared by S3 and local write)."""
    if not rows:
        return pa.table({})
    return pa.table(
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


def _write_parquet_to_s3(
    rows: list[dict[str, Any]],
    bucket: str,
    key: str,
    s3_client: Any,
) -> None:
    """Write rows as a parquet file to S3."""
    if not rows:
        return
    table = _rows_to_parquet_table(rows)
    buf = BytesIO()
    pq.write_table(table, buf)
    buf.seek(0)
    s3_client.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())


def _write_parquet_to_file(rows: list[dict[str, Any]], path: Path) -> None:
    """Write rows as a parquet file to the local filesystem."""
    if not rows:
        return
    table = _rows_to_parquet_table(rows)
    pq.write_table(table, path)


def _run_s3(prefix: str) -> int:
    """
    List transcript JSONs under S3 prefix, compute speaker stats, write parquet to S3.

    Args:
        prefix: S3 URI (e.g. s3://bucket/jobs/id/transcripts).

    Returns:
        Number of parquet files written.
    """
    bucket, prefix_key = _parse_s3_uri(prefix)
    if not prefix_key.endswith("/"):
        prefix_key += "/"
    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix_key):
        for obj in page.get("Contents") or []:
            key = obj["Key"]
            if not key.endswith("_transcription.json"):
                continue
            stem = key.rsplit("/", 1)[-1].replace("_transcription.json", "")
            try:
                resp = client.get_object(Bucket=bucket, Key=key)
                body = resp["Body"].read().decode("utf-8")
                data = json.loads(body)
            except Exception as e:
                print(f"Warning: failed to read {key}: {e}", file=sys.stderr)
                continue
            transcription = data.get("transcription") or []
            rows = _compute_speaker_stats(transcription)
            if not rows:
                continue
            parquet_key = prefix_key + stem + "_speaker_stats.parquet"
            _write_parquet_to_s3(rows, bucket, parquet_key, client)
            count += 1
            print(f"Wrote {parquet_key}")
    return count


def _run_local(dir_path: Path) -> int:
    """
    List *_transcription.json in directory, compute speaker stats, write parquet locally.

    Args:
        dir_path: Directory containing transcript JSON files.

    Returns:
        Number of parquet files written.
    """
    if not dir_path.is_dir():
        print(f"Error: not a directory: {dir_path}", file=sys.stderr)
        return 0
    count = 0
    for path in sorted(dir_path.glob("*_transcription.json")):
        stem = path.stem.replace("_transcription", "")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Warning: failed to read {path}: {e}", file=sys.stderr)
            continue
        transcription = data.get("transcription") or []
        rows = _compute_speaker_stats(transcription)
        if not rows:
            continue
        out_path = dir_path / f"{stem}_speaker_stats.parquet"
        _write_parquet_to_file(rows, out_path)
        count += 1
        print(f"Wrote {out_path}")
    return count


def run(prefix: str) -> int:
    """
    List transcript JSONs under prefix, compute speaker stats, write parquet.

    Prefix may be an S3 URI (s3://bucket/key) or a local path (file:///path or
    /path). For local paths, reads and writes in that directory.

    Args:
        prefix: S3 prefix or local directory path.

    Returns:
        Number of parquet files written (0 on error or no files).
    """
    prefix = prefix.strip()
    if prefix.startswith("s3://"):
        return _run_s3(prefix)
    # Local: strip file:// and resolve to absolute path
    if prefix.startswith("file://"):
        dir_path = Path(prefix[7:])
    else:
        dir_path = Path(prefix)
    dir_path = dir_path.resolve()
    return _run_local(dir_path)


def main() -> None:
    """Entry point: read TRANSCRIPTS_S3_PREFIX or TRANSCRIPTS_PREFIX from env and run."""
    prefix = (
        os.environ.get("TRANSCRIPTS_S3_PREFIX") or os.environ.get("TRANSCRIPTS_PREFIX")
        or ""
    ).strip()
    if not prefix:
        print(
            "Error: TRANSCRIPTS_S3_PREFIX or TRANSCRIPTS_PREFIX must be set",
            file=sys.stderr,
        )
        sys.exit(1)
    n = run(prefix)
    print(f"Done. Wrote {n} parquet file(s).")


if __name__ == "__main__":
    main()
