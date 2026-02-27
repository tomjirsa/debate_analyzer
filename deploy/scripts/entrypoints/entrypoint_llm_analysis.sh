#!/usr/bin/env bash
# LLM analysis job: read transcript(s) from S3 or env, run analysis, write _llm_analysis.json.
# Runs on CPU (Transformers backend). Requires env: TRANSCRIPT_S3_URI (single file) or TRANSCRIPTS_S3_PREFIX (S3 prefix).
# Optional: LLM_MODEL_ID (default Qwen/Qwen2-1.5B-Instruct), LLM_MAX_MODEL_LEN (default 8192), MOCK_LLM=1 for tests.

set -euo pipefail

if [[ -n "${TRANSCRIPT_S3_URI:-}" ]]; then
  echo "Running LLM analysis for transcript: $TRANSCRIPT_S3_URI"
elif [[ -n "${TRANSCRIPTS_S3_PREFIX:-}" ]]; then
  echo "Running LLM analysis for transcripts under: $TRANSCRIPTS_S3_PREFIX"
else
  echo "Error: TRANSCRIPT_S3_URI or TRANSCRIPTS_S3_PREFIX must be set" >&2
  exit 1
fi

python -m debate_analyzer.batch.llm_analysis_job

echo "Done."
