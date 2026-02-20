#!/usr/bin/env bash
# Job 3: Read transcript JSON from S3 prefix, compute per-speaker stats, write parquet to same prefix.
# Requires env: TRANSCRIPTS_S3_PREFIX (e.g. s3://bucket/jobs/id/transcripts).

set -euo pipefail

if [[ -z "${TRANSCRIPTS_S3_PREFIX:-}" ]]; then
  echo "Error: TRANSCRIPTS_S3_PREFIX must be set" >&2
  exit 1
fi

echo "Computing speaker stats from $TRANSCRIPTS_S3_PREFIX"
python -m debate_analyzer.batch.stats_job

echo "Done. Parquet files written under $TRANSCRIPTS_S3_PREFIX"
