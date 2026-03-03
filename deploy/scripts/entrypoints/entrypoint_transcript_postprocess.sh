#!/usr/bin/env bash
# Transcript postprocess job (Ollama): reads *_transcription_raw.json, writes *_transcription.json.
# Requires env: TRANSCRIPT_S3_URI (single file) or TRANSCRIPTS_S3_PREFIX (S3 prefix).
# Same Ollama setup as LLM analysis job.

set -euo pipefail

if [[ -n "${TRANSCRIPT_S3_URI:-}" ]]; then
  echo "Running transcript postprocess (Ollama) for: $TRANSCRIPT_S3_URI"
elif [[ -n "${TRANSCRIPTS_S3_PREFIX:-}" ]]; then
  echo "Running transcript postprocess (Ollama) for prefix: $TRANSCRIPTS_S3_PREFIX"
else
  echo "Error: TRANSCRIPT_S3_URI or TRANSCRIPTS_S3_PREFIX must be set" >&2
  exit 1
fi

export OLLAMA_MODELS="${OLLAMA_MODELS:-/cache/ollama}"
export LLM_BACKEND=ollama
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_CONTEXT_LENGTH="${LLM_MAX_MODEL_LEN:-4096}"

mkdir -p "$OLLAMA_MODELS"

echo "Starting Ollama in background (models at $OLLAMA_MODELS, context=${OLLAMA_CONTEXT_LENGTH})..."
ollama serve &
OLLAMA_PID=$!

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

OLLAMA_MODEL="${OLLAMA_MODEL:-${LLM_MODEL_ID:-qwen2.5:7b}}"
echo "Pulling model $OLLAMA_MODEL (if not cached)..."
ollama pull "$OLLAMA_MODEL" || true

echo "Starting transcript postprocess (logs prefixed with [LLM])."
exec python3 -m debate_analyzer.batch.transcript_postprocess_job
