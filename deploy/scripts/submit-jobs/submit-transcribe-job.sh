#!/usr/bin/env bash
# Submit an AWS Batch job to transcribe a video already in S3 (Job 2).
# Usage: ./submit-transcribe-job.sh <video_s3_prefix> [output_s3_prefix]
# Example: ./submit-transcribe-job.sh s3://bucket/jobs/job-id-123/videos
#          ./submit-transcribe-job.sh s3://bucket/jobs/job-id-123/videos s3://bucket/jobs/job-id-123
# If output_s3_prefix is omitted, it is derived by stripping /videos from video_s3_prefix (if present) or using the parent path.

set -euo pipefail

if [[ $# -lt 1 ]] || [[ -z "${1:-}" ]]; then
  echo "Usage: $0 <video_s3_prefix> [output_s3_prefix]" >&2
  echo "Example: $0 s3://bucket/jobs/job-id-123/videos" >&2
  echo "         $0 s3://bucket/jobs/job-id-123/videos s3://bucket/jobs/job-id-123" >&2
  exit 1
fi

VIDEO_S3_PREFIX="$1"
if [[ $# -ge 2 ]] && [[ -n "${2:-}" ]]; then
  OUTPUT_S3_PREFIX="$2"
else
  # Derive output prefix: s3://bucket/jobs/id/videos -> s3://bucket/jobs/id
  if [[ "$VIDEO_S3_PREFIX" == */videos ]]; then
    OUTPUT_S3_PREFIX="${VIDEO_S3_PREFIX%/videos}"
  elif [[ "$VIDEO_S3_PREFIX" == */videos/ ]]; then
    OUTPUT_S3_PREFIX="${VIDEO_S3_PREFIX%/videos/}"
  else
    OUTPUT_S3_PREFIX="$VIDEO_S3_PREFIX"
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../../terraform"

if [[ ! -d "$TERRAFORM_DIR" ]]; then
  echo "Error: Terraform directory not found: $TERRAFORM_DIR" >&2
  exit 1
fi

echo "Resolving Terraform outputs..."
cd "$TERRAFORM_DIR"
QUEUE=$(terraform output -raw batch_job_queue_name)
DEFN=$(terraform output -raw batch_job_definition_transcribe_name)
REGION=$(terraform output -raw aws_region)

JOB_NAME="debate-analyzer-transcribe-$(date +%s)"
echo "Submitting transcribe job: $JOB_NAME"
echo "Video S3 prefix: $VIDEO_S3_PREFIX"
echo "Output S3 prefix (transcripts): $OUTPUT_S3_PREFIX/transcripts/"

aws batch submit-job \
  --job-name "$JOB_NAME" \
  --job-queue "$QUEUE" \
  --job-definition "$DEFN" \
  --container-overrides "{\"environment\":[{\"name\":\"VIDEO_S3_PREFIX\",\"value\":\"$VIDEO_S3_PREFIX\"},{\"name\":\"OUTPUT_S3_PREFIX\",\"value\":\"$OUTPUT_S3_PREFIX\"}]}" \
  --region "$REGION"

echo "Job submitted successfully."
