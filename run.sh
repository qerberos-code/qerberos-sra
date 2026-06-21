#!/bin/sh
#
# Run the security review agent.
#
# Usage:
#   ./run.sh [REPO_PATH] [-o OUTPUT_DIR] [-p "extra instructions"]
#
# Examples:
#   ./run.sh                       # review the current directory
#   ./run.sh ../some-project       # review another repo
#   ./run.sh . -o reports          # write reports into ./reports

set -e

SCRIPT_DIR="$(dirname "$0")"
PYTHONSAFEPATH=1 PYTHONPATH="$SCRIPT_DIR" exec uv run \
  --project "$SCRIPT_DIR" \
  --quiet \
  -m app.main \
  "$@"
