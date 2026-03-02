#!/usr/bin/env bash
# LLM analysis job with Ollama: start ollama serve, wait for API, then run Python job.
# Requires env: TRANSCRIPT_S3_URI (single file) or TRANSCRIPTS_S3_PREFIX (S3 prefix).
# Sets LLM_BACKEND=ollama and OLLAMA_HOST=http://localhost:11434.
# Optional: OLLAMA_MODELS (default /cache/ollama for EFS), OLLAMA_MODEL or LLM_MODEL_ID (e.g. qwen2.5:7b).

set -euo pipefail

if [[ -n "${TRANSCRIPT_S3_URI:-}" ]]; then
  echo "Running LLM analysis (Ollama) for transcript: $TRANSCRIPT_S3_URI"
elif [[ -n "${TRANSCRIPTS_S3_PREFIX:-}" ]]; then
  echo "Running LLM analysis (Ollama) for transcripts under: $TRANSCRIPTS_S3_PREFIX"
else
  echo "Error: TRANSCRIPT_S3_URI or TRANSCRIPTS_S3_PREFIX must be set" >&2
  exit 1
fi

export OLLAMA_MODELS="${OLLAMA_MODELS:-/cache/ollama}"
export LLM_BACKEND=ollama
export OLLAMA_HOST=http://localhost:11434
# So Ollama server uses same context as the job (avoids truncation when prompts exceed default 2048)
export OLLAMA_CONTEXT_LENGTH="${LLM_MAX_MODEL_LEN:-4096}"

mkdir -p "$OLLAMA_MODELS"

echo "Starting Ollama in background (models at $OLLAMA_MODELS, context=${OLLAMA_CONTEXT_LENGTH})..."
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama API to be ready (timeout 60s)
echo "Waiting for Ollama API..."
for i in $(seq 1 60); do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:11434/api/tags 2>/dev/null | grep -q 200; then
    echo "Ollama API is ready."
    break
  fi
  if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
    echo "Error: Ollama process exited unexpectedly" >&2
    exit 1
  fi
  sleep 1
done

if ! curl -s -o /dev/null -w "%{http_code}" http://localhost:11434/api/tags 2>/dev/null | grep -q 200; then
  echo "Error: Ollama API did not become ready in time" >&2
  kill "$OLLAMA_PID" 2>/dev/null || true
  exit 1
fi

# Ensure model is present (idempotent; uses EFS cache after first pull)
OLLAMA_MODEL="${OLLAMA_MODEL:-${LLM_MODEL_ID:-qwen2.5:7b}}"
echo "Pulling model $OLLAMA_MODEL (if not cached)..."
ollama pull "$OLLAMA_MODEL" || true

echo "Starting Python job (logs prefixed with [LLM])."
exec python3 -m debate_analyzer.batch.llm_analysis_job
