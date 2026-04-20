#!/bin/bash
# tools/cleanup.sh - Clean up build artifacts and test installations

set -e

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE_DIR"

echo "Cleaning up build artifacts..."

# Remove build directories
rm -rf dist/
rm -rf build/
rm -rf *.egg-info/

# Remove test installations
if command -v uv &> /dev/null; then
    echo "Removing test virtual environments..."
    uv python uninstall 3.9 2>/dev/null || true
fi

echo "Cleanup complete."
