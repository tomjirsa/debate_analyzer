#!/usr/bin/env bash
# Transcript postprocess job (CPU): reads *_transcription_raw.json, writes *_transcription.json.
# Requires env: TRANSCRIPT_S3_URI (single file) or TRANSCRIPTS_S3_PREFIX (S3 prefix).
# Aggregates consecutive same-speaker segments; no GPU or LLM.

set -euo pipefail

if [[ -n "${TRANSCRIPT_S3_URI:-}" ]]; then
  echo "Running transcript postprocess for: $TRANSCRIPT_S3_URI"
elif [[ -n "${TRANSCRIPTS_S3_PREFIX:-}" ]]; then
  echo "Running transcript postprocess for prefix: $TRANSCRIPTS_S3_PREFIX"
else
  echo "Error: TRANSCRIPT_S3_URI or TRANSCRIPTS_S3_PREFIX must be set" >&2
  exit 1
fi

exec python3 -m debate_analyzer.batch.transcript_postprocess_job
