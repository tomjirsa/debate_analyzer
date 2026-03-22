#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"

usage() {
  echo "Usage: $0 <path-to*_transcription.json> [OLLAMA_MODEL]" >&2
  echo "  Default OLLAMA_MODEL: llama3.2" >&2
  exit 1
}

[[ $# -lt 1 ]] && usage

TRANSCRIPT="$1"
MODEL="${2:-llama3.2}"

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
exec poetry run python -m debate_analyzer.batch.llm_analysis_job
