#!/usr/bin/env bash
# Job 1: Download video from URL and upload to S3.
# Requires env: VIDEO_URL, OUTPUT_S3_PREFIX. Optional: AWS_BATCH_JOB_ID (used for unique path).
# Optional: YT_COOKIES_SECRET_ARN or YT_COOKIES_S3_URI for YouTube bot check.

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

# Optional cookies for YouTube (bot check on datacenter IPs).
COOKIES_LOCAL=/tmp/yt_cookies.txt
if [[ -n "${YT_COOKIES_SECRET_ARN:-}" ]]; then
  aws secretsmanager get-secret-value --secret-id "$YT_COOKIES_SECRET_ARN" --query SecretString --output text > "$COOKIES_LOCAL"
  export YT_COOKIES_FILE="$COOKIES_LOCAL"
elif [[ -n "${YT_COOKIES_S3_URI:-}" ]]; then
  aws s3 cp "$YT_COOKIES_S3_URI" "$COOKIES_LOCAL"
  export YT_COOKIES_FILE="$COOKIES_LOCAL"
fi

echo "Step 1/2: Downloading video from $VIDEO_URL"
python -m debate_analyzer.video_downloader "$VIDEO_URL" --output-dir "$DOWNLOADS_DIR"

echo "Step 2/2: Uploading downloaded video and subtitles to S3 ($PREFIX/videos/)"
aws s3 sync "$DOWNLOADS_DIR" "$PREFIX/videos/" --no-progress

echo "Done. Videos: $PREFIX/videos/"
