#!/usr/bin/env bash
# Job 2: Load video from S3 prefix, transcribe with GPU, upload transcripts to S3.
# Requires env: VIDEO_S3_PREFIX (e.g. s3://bucket/jobs/id/videos/), OUTPUT_S3_PREFIX (e.g. s3://bucket/jobs/id).
# HF_TOKEN is injected by Batch from Secrets Manager.

set -euo pipefail

if [[ -z "${VIDEO_S3_PREFIX:-}" ]] || [[ -z "${OUTPUT_S3_PREFIX:-}" ]]; then
  echo "Error: VIDEO_S3_PREFIX and OUTPUT_S3_PREFIX must be set" >&2
  exit 1
fi

INPUT_DIR=/tmp/input
TRANSCRIPT_DIR=/tmp/out

echo "Step 1/3: Syncing video from S3 ($VIDEO_S3_PREFIX) to local"
mkdir -p "$INPUT_DIR"
aws s3 sync "$VIDEO_S3_PREFIX" "$INPUT_DIR/" --no-progress

VIDEO_FILE=$(find "$INPUT_DIR" -type f \( -name "*.mp4" -o -name "*.mkv" -o -name "*.webm" \) | head -1)
if [[ -z "$VIDEO_FILE" ]] || [[ ! -f "$VIDEO_FILE" ]]; then
  echo "Error: No video file found under $INPUT_DIR" >&2
  exit 1
fi

echo "Step 2/3: Transcribing audio (GPU)"
mkdir -p "$TRANSCRIPT_DIR"
python -m debate_analyzer.transcriber "$VIDEO_FILE" --output-dir "$TRANSCRIPT_DIR" --device cuda

echo "Step 3/3: Uploading transcripts to S3 ($OUTPUT_S3_PREFIX/transcripts/)"
aws s3 sync "$TRANSCRIPT_DIR" "$OUTPUT_S3_PREFIX/transcripts/" --no-progress

echo "Done. Transcripts: $OUTPUT_S3_PREFIX/transcripts/"
