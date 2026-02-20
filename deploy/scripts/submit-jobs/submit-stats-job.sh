#!/usr/bin/env bash
# Submit an AWS Batch job to compute speaker stats from transcript JSON in S3 (Job 3).
# Usage: ./submit-stats-job.sh <transcripts_s3_prefix>
# Example: ./submit-stats-job.sh s3://bucket/jobs/job-id-123/transcripts
# Run after the transcribe job has written transcripts to that prefix.

set -euo pipefail

if [[ $# -lt 1 ]] || [[ -z "${1:-}" ]]; then
  echo "Usage: $0 <transcripts_s3_prefix>" >&2
  echo "Example: $0 s3://bucket/jobs/job-id-123/transcripts" >&2
  exit 1
fi

TRANSCRIPTS_S3_PREFIX="$1"
# Ensure trailing slash for prefix
if [[ "$TRANSCRIPTS_S3_PREFIX" != */ ]]; then
  TRANSCRIPTS_S3_PREFIX="${TRANSCRIPTS_S3_PREFIX}/"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../../terraform"

if [[ ! -d "$TERRAFORM_DIR" ]]; then
  echo "Error: Terraform directory not found: $TERRAFORM_DIR" >&2
  exit 1
fi

echo "Resolving Terraform outputs..."
cd "$TERRAFORM_DIR"
QUEUE=$(terraform output -raw batch_job_queue_cpu_name)
DEFN=$(terraform output -raw batch_job_definition_stats_name)
REGION=$(terraform output -raw aws_region)

JOB_NAME="debate-analyzer-stats-$(date +%s)"
echo "Submitting stats job: $JOB_NAME"
echo "Transcripts S3 prefix: $TRANSCRIPTS_S3_PREFIX"

aws batch submit-job \
  --job-name "$JOB_NAME" \
  --job-queue "$QUEUE" \
  --job-definition "$DEFN" \
  --container-overrides "{\"environment\":[{\"name\":\"TRANSCRIPTS_S3_PREFIX\",\"value\":\"$TRANSCRIPTS_S3_PREFIX\"}]}" \
  --region "$REGION"

echo "Job submitted successfully."
