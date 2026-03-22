#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"

usage() {
  echo "Usage: $0 <path-to*_transcription.json> [OLLAMA_MODEL]" >&2
  echo "  Default OLLAMA_MODEL: llama3.2:3b (with max context: 131072 tokens)" >&2
  echo "  Set LLAMA_MAX_CONTEXT=0 to skip LLM_MAX_MODEL_LEN / chunk exports (use job defaults)." >&2
  exit 1
}

[[ $# -lt 1 ]] && usage

TRANSCRIPT="$1"
MODEL="${2:-llama3.2:3b}"

if [[ ! -f "$TRANSCRIPT" ]]; then
  echo "Error: file not found: $TRANSCRIPT" >&2
  exit 1
fi

case "$TRANSCRIPT" in
*_transcription.json) ;;
*)
  echo "Error: filename must contain _transcription.json (job single-file mode)." >&2
  exit 1
  ;;
esac

ABS="$(cd "$(dirname "$TRANSCRIPT")" && pwd)/$(basename "$TRANSCRIPT")"

cd "$REPO_ROOT"
export TRANSCRIPT_S3_URI="$ABS"
export OLLAMA_MODEL="$MODEL"

# Max context for Llama 3.2 3B (align OLLAMA_CONTEXT_LENGTH when starting ollama serve).
if [[ "${LLAMA_MAX_CONTEXT:-1}" != "0" ]]; then
  export LLM_MAX_MODEL_LEN="${LLM_MAX_MODEL_LEN:-131072}"
  export LLM_PHASE1_MAX_CHUNK_TOKENS="${LLM_PHASE1_MAX_CHUNK_TOKENS:-131072}"
  export LLM_OLLAMA_MAX_CONTENT_TOKENS="${LLM_OLLAMA_MAX_CONTENT_TOKENS:-127572}"
fi

exec poetry run python -m debate_analyzer.batch.llm_analysis_job
