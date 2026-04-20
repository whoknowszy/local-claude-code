#!/usr/bin/env bash
# Update LCCG from the local source checkout used by install.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="${LCCG_SOURCE_DIR:-$REPO_DIR}"

if [[ ! -d "$SRC_DIR/.git" || ! -f "$SRC_DIR/pyproject.toml" ]]; then
    SRC_DIR="$HOME/.lccg/source"
fi

if [[ ! -d "$SRC_DIR/.git" || ! -f "$SRC_DIR/pyproject.toml" ]]; then
    echo "[ERROR] Cannot find a local LCCG source checkout." >&2
    echo "        Reinstall with install.sh, or set LCCG_SOURCE_DIR=/path/to/local-claude-code." >&2
    exit 1
fi

PYTHON_CMD="${PYTHON:-}"
if [[ -z "$PYTHON_CMD" ]]; then
    for cmd in python3.12 python3.11 python3.10 python3.9 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            PYTHON_CMD="$cmd"
            break
        fi
    done
fi

if [[ -z "$PYTHON_CMD" ]]; then
    echo "[ERROR] Python 3.9+ is required." >&2
    exit 1
fi

echo "[INFO] Updating source checkout: $SRC_DIR"
git -C "$SRC_DIR" pull --ff-only origin main

echo "[INFO] Reinstalling editable package..."
$PYTHON_CMD -m pip install -e "$SRC_DIR"

echo "[OK] Update complete."
lccg --version 2>/dev/null || true
