#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

: "${ADMIN_USERNAME:?ADMIN_USERNAME must be set}"
: "${ADMIN_PASSWORD:?ADMIN_PASSWORD must be set}"

cd "$REPO_ROOT"
ADMIN_USERNAME="$ADMIN_USERNAME" ADMIN_PASSWORD="$ADMIN_PASSWORD" make webapp-api

