#!/usr/bin/env bash
# Submit an AWS Batch job to download a video from URL and upload to S3 (Job 1).
# Usage: ./submit-download-job.sh <video_url>
# Example: ./submit-download-job.sh "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
# After the job completes, use submit-transcribe-job.sh with the job ID to transcribe.

set -euo pipefail

if [[ $# -lt 1 ]] || [[ -z "${1:-}" ]]; then
  echo "Usage: $0 <video_url>" >&2
  echo "Example: $0 'https://www.youtube.com/watch?v=YOUR_VIDEO_ID'" >&2
  exit 1
fi

VIDEO_URL="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"

if [[ ! -d "$TERRAFORM_DIR" ]]; then
  echo "Error: Terraform directory not found: $TERRAFORM_DIR" >&2
  exit 1
fi

echo "Resolving Terraform outputs..."
cd "$TERRAFORM_DIR"
QUEUE=$(terraform output -raw batch_job_queue_cpu_name)
DEFN=$(terraform output -raw batch_job_definition_download_name)
BUCKET=$(terraform output -raw s3_bucket_name)
REGION=$(terraform output -raw aws_region)

JOB_NAME="debate-analyzer-download-$(date +%s)"
echo "Submitting download job: $JOB_NAME"
echo "Video URL: $VIDEO_URL"
echo "Output prefix: s3://$BUCKET/jobs"
echo "After completion, run: $SCRIPT_DIR/submit-transcribe-job.sh s3://$BUCKET/jobs/<JOB_ID>/videos"

aws batch submit-job \
  --job-name "$JOB_NAME" \
  --job-queue "$QUEUE" \
  --job-definition "$DEFN" \
  --container-overrides "{\"environment\":[{\"name\":\"VIDEO_URL\",\"value\":\"$VIDEO_URL\"},{\"name\":\"OUTPUT_S3_PREFIX\",\"value\":\"s3://$BUCKET/jobs\"}]}" \
  --region "$REGION"

echo "Job submitted successfully. Note the job ID to pass to submit-transcribe-job.sh."
