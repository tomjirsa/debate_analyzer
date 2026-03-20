#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

cd "$REPO_ROOT"

# Uses the current DB connection (default sqlite:///./debate_analyzer.db) by
# not setting DATABASE_URL.
exec poetry run python -m debate_analyzer.scripts.upload_local_data_to_db --data-root "./data" "$@"

