#!/usr/bin/env bash
# Pipeline wrapper for AWS Batch: download video from URL -> upload to S3 -> transcribe -> upload transcripts to S3.
# Requires env: VIDEO_URL, OUTPUT_S3_PREFIX. Optional: AWS_BATCH_JOB_ID (used for unique path).
# HF_TOKEN is injected by Batch from Secrets Manager.

set -euo pipefail

if [[ -z "${VIDEO_URL:-}" ]] || [[ -z "${OUTPUT_S3_PREFIX:-}" ]]; then
  echo "Error: VIDEO_URL and OUTPUT_S3_PREFIX must be set" >&2
  exit 1
fi

# Use job ID for a unique prefix per job so multiple runs do not overwrite
if [[ -n "${AWS_BATCH_JOB_ID:-}" ]]; then
  PREFIX="${OUTPUT_S3_PREFIX}/${AWS_BATCH_JOB_ID}"
else
  PREFIX="$OUTPUT_S3_PREFIX"
fi

DOWNLOADS_DIR=/tmp/downloads
TRANSCRIPT_DIR=/tmp/out

echo "Step 1/4: Downloading video from $VIDEO_URL"
python -m debate_analyzer.video_downloader "$VIDEO_URL" --output-dir "$DOWNLOADS_DIR"

# Resolve path to the downloaded video (downloader writes to output_dir/videos/)
VIDEO_FILE=$(find "$DOWNLOADS_DIR" -type f \( -name "*.mp4" -o -name "*.mkv" -o -name "*.webm" \) | head -1)
if [[ -z "$VIDEO_FILE" ]] || [[ ! -f "$VIDEO_FILE" ]]; then
  echo "Error: No video file found under $DOWNLOADS_DIR" >&2
  exit 1
fi

echo "Step 2/4: Uploading downloaded video and subtitles to S3 ($PREFIX/videos/)"
aws s3 sync "$DOWNLOADS_DIR" "$PREFIX/videos/" --no-progress

echo "Step 3/4: Transcribing audio (GPU)"
mkdir -p "$TRANSCRIPT_DIR"
python -m debate_analyzer.transcriber "$VIDEO_FILE" --output-dir "$TRANSCRIPT_DIR" --device cuda

echo "Step 4/4: Uploading transcripts to S3 ($PREFIX/transcripts/)"
aws s3 sync "$TRANSCRIPT_DIR" "$PREFIX/transcripts/" --no-progress

echo "Done. Videos: $PREFIX/videos/  Transcripts: $PREFIX/transcripts/"
