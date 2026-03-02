#!/usr/bin/env bash
# Submit an AWS Batch job to run LLM analysis (Ollama) on a transcript (Job 4).
# Usage: ./submit-llm-analysis-job.sh <transcript_s3_uri_or_prefix>
# Example: ./submit-llm-analysis-job.sh s3://bucket/jobs/job-id-123/transcripts/foo_transcription.json
# Or:      ./submit-llm-analysis-job.sh s3://bucket/jobs/job-id-123/transcripts
# Job runs on the GPU queue. Requires the Ollama LLM image (Dockerfile.llm.ollama) pushed to the debate-analyzer-llm ECR repo with tag latest-ollama.

set -euo pipefail

if [[ $# -lt 1 ]] || [[ -z "${1:-}" ]]; then
  echo "Usage: $0 <transcript_s3_uri_or_prefix>" >&2
  echo "Example: $0 s3://bucket/jobs/job-id-123/transcripts/foo_transcription.json" >&2
  echo "Or:      $0 s3://bucket/jobs/job-id-123/transcripts" >&2
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
QUEUE=$(terraform output -raw batch_job_queue_name)
DEFN=$(terraform output -raw batch_job_definition_llm_analysis_name)

if [[ "$TRANSCRIPT_URI" == *"_transcription.json"* ]]; then
  ENV_NAME="TRANSCRIPT_S3_URI"
else
  ENV_NAME="TRANSCRIPTS_S3_PREFIX"
fi

JOB_NAME="debate-analyzer-llm-$(date +%s)"
echo "Submitting LLM analysis job (Ollama): $JOB_NAME"
echo "$ENV_NAME=$TRANSCRIPT_URI"

aws batch submit-job \
  --job-name "$JOB_NAME" \
  --job-queue "$QUEUE" \
  --job-definition "$DEFN" \
  --container-overrides "{\"environment\":[{\"name\":\"$ENV_NAME\",\"value\":\"$TRANSCRIPT_URI\"}]}" \
  --region "$REGION"

echo "Job submitted successfully."
