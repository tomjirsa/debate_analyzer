#!/usr/bin/env bash
# Submit an AWS Batch job to run LLM analysis on a transcript (Job 4).
# Usage: ./submit-llm-analysis-job.sh [--gpu] <transcript_s3_uri>
#   --gpu    Use GPU queue and GPU job definition (launches GPU instance; requires LLM GPU image).
#   Without --gpu: runs on CPU queue (no GPU instance).
# Example: ./submit-llm-analysis-job.sh s3://bucket/jobs/job-id-123/transcripts/foo_transcription.json
# Example: ./submit-llm-analysis-job.sh --gpu s3://bucket/jobs/job-id-123/transcripts
# Requires the LLM image (CPU and/or GPU) to be built and pushed to the debate-analyzer-llm ECR repo.

set -euo pipefail

USE_GPU=false
TRANSCRIPT_URI=""
for arg in "$@"; do
  if [[ "$arg" == "--gpu" ]]; then
    USE_GPU=true
  else
    TRANSCRIPT_URI="$arg"
  fi
done

if [[ -z "$TRANSCRIPT_URI" ]]; then
  echo "Usage: $0 [--gpu] <transcript_s3_uri_or_prefix>" >&2
  echo "  --gpu  Submit to GPU queue (faster; requires LLM GPU image tag latest-gpu)." >&2
  echo "Example: $0 s3://bucket/jobs/job-id-123/transcripts/foo_transcription.json" >&2
  echo "Example: $0 --gpu s3://bucket/jobs/job-id-123/transcripts" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../../terraform"

if [[ ! -d "$TERRAFORM_DIR" ]]; then
  echo "Error: Terraform directory not found: $TERRAFORM_DIR" >&2
  exit 1
fi

echo "Resolving Terraform outputs..."
cd "$TERRAFORM_DIR"
REGION=$(terraform output -raw aws_region)
if [[ "$USE_GPU" == "true" ]]; then
  QUEUE=$(terraform output -raw batch_job_queue_name)
  DEFN=$(terraform output -raw batch_job_definition_llm_analysis_gpu_name)
else
  QUEUE=$(terraform output -raw batch_job_queue_llm_name)
  DEFN=$(terraform output -raw batch_job_definition_llm_analysis_name)
fi

if [[ "$TRANSCRIPT_URI" == *"_transcription.json"* ]]; then
  ENV_NAME="TRANSCRIPT_S3_URI"
else
  ENV_NAME="TRANSCRIPTS_S3_PREFIX"
fi

if [[ "$USE_GPU" == "true" ]]; then
  JOB_NAME="debate-analyzer-llm-gpu-$(date +%s)"
  echo "Submitting LLM analysis job (GPU queue): $JOB_NAME"
else
  JOB_NAME="debate-analyzer-llm-$(date +%s)"
  echo "Submitting LLM analysis job (CPU queue): $JOB_NAME"
fi
echo "$ENV_NAME=$TRANSCRIPT_URI"

aws batch submit-job \
  --job-name "$JOB_NAME" \
  --job-queue "$QUEUE" \
  --job-definition "$DEFN" \
  --container-overrides "{\"environment\":[{\"name\":\"$ENV_NAME\",\"value\":\"$TRANSCRIPT_URI\"}]}" \
  --region "$REGION"

echo "Job submitted successfully."
