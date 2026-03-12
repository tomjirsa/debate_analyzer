#!/usr/bin/env bash
# Submit an AWS Batch job to run transcript postprocess on raw transcripts (Job 5).
# Usage: ./submit-transcript-postprocess-job.sh <transcript_s3_uri_or_prefix>
# Example (single file): ./submit-transcript-postprocess-job.sh s3://bucket/jobs/id/transcripts/foo_transcription_raw.json
# Example (prefix):      ./submit-transcript-postprocess-job.sh s3://bucket/jobs/id/transcripts
# Job reads *_transcription_raw.json and writes *_transcription.json. Runs on CPU queue.

set -euo pipefail

if [[ $# -lt 1 ]] || [[ -z "${1:-}" ]]; then
  echo "Usage: $0 <transcript_s3_uri_or_prefix>" >&2
  echo "Example (single file): $0 s3://bucket/jobs/id/transcripts/foo_transcription_raw.json" >&2
  echo "Example (prefix):      $0 s3://bucket/jobs/id/transcripts" >&2
  exit 1
fi

TRANSCRIPT_URI="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../../terraform"

if [[ ! -d "$TERRAFORM_DIR" ]]; then
  echo "Error: Terraform directory not found: $TERRAFORM_DIR" >&2
  exit 1
fi

echo "Resolving Terraform outputs..."
cd "$TERRAFORM_DIR"
REGION=$(terraform output -raw aws_region)
QUEUE=$(terraform output -raw batch_job_queue_cpu_name)
DEFN=$(terraform output -raw batch_job_definition_transcript_postprocess_name)

if [[ "$TRANSCRIPT_URI" == *"_transcription_raw.json"* ]]; then
  ENV_NAME="TRANSCRIPT_S3_URI"
else
  ENV_NAME="TRANSCRIPTS_S3_PREFIX"
fi

JOB_NAME="debate-analyzer-postprocess-$(date +%s)"
echo "Submitting transcript postprocess job (CPU queue): $JOB_NAME"
echo "$ENV_NAME=$TRANSCRIPT_URI"

aws batch submit-job \
  --job-name "$JOB_NAME" \
  --job-queue "$QUEUE" \
  --job-definition "$DEFN" \
  --container-overrides "{\"environment\":[{\"name\":\"$ENV_NAME\",\"value\":\"$TRANSCRIPT_URI\"}]}" \
  --region "$REGION"

echo "Job submitted successfully."
