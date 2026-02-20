"""
Compute per-speaker statistics per transcript and write to parquet in S3.

Reads TRANSCRIPTS_S3_PREFIX from the environment, lists *_transcription.json objects,
aggregates per-speaker stats (total_seconds, segment_count, word_count) per file,
and writes <stem>_speaker_stats.parquet to the same S3 prefix.

Invoked by the stats Batch job entrypoint
(e.g. python -m debate_analyzer.batch.stats_job).
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from io import BytesIO
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


def _write_parquet_to_s3(
    rows: list[dict[str, Any]],
    bucket: str,
    key: str,
    s3_client: Any,
) -> None:
    """Write rows as a parquet file to S3."""
    if not rows:
        return
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
    buf = BytesIO()
    pq.write_table(table, buf)
    buf.seek(0)
    s3_client.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())


def run(prefix: str) -> int:
    """
    List transcript JSONs under prefix, compute speaker stats,
    write parquet to same prefix.

    Args:
        prefix: S3 prefix (e.g. s3://bucket/jobs/id/transcripts).

    Returns:
        Number of parquet files written (0 on error or no files).
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


def main() -> None:
    """Entry point: read TRANSCRIPTS_S3_PREFIX from env and run."""
    prefix = os.environ.get("TRANSCRIPTS_S3_PREFIX", "").strip()
    if not prefix:
        print("Error: TRANSCRIPTS_S3_PREFIX must be set", file=sys.stderr)
        sys.exit(1)
    n = run(prefix)
    print(f"Done. Wrote {n} parquet file(s).")


if __name__ == "__main__":
    main()
