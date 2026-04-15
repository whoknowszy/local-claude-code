#!/bin/bash
# tools/build.pyz.sh - Build standalone pyz using uv

set -e

LATEST_VERSION="0.4.1"
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE_DIR"

echo "Building lccg v${LATEST_VERSION} pyz..."

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Build pyz
uv build --pyz lccg-${LATEST_VERSION}.pyz

echo "Pyz built successfully: dist/lccg-${LATEST_VERSION}.pyz"