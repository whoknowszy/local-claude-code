#!/bin/bash
# tools/upload-release.sh - Manual GitHub release uploader

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <tag_name>"
    echo "Example: $0 v0.4.1"
    exit 1
fi

TAG_NAME="$1"
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE_DIR"

echo "Uploading release for tag: $TAG_NAME"

# Build all pyz files first
echo "Building pyz files..."
./tools/build.pyz.sh

# Upload to GitHub releases using gh CLI or API
if command -v gh &> /dev/null; then
    echo "Uploading via gh CLI..."
    gh release create "$TAG_NAME" \
        dist/*.whl \
        dist/*.tar.gz \
        pyz-artifacts/*.pyz \
        --title "$TAG_NAME" \
        --generate-notes
else
    echo "gh CLI not found. Please upload manually at:"
    echo "https://github.com/whoknowszy/local-claude-code/releases/new?tag=$TAG_NAME"
    echo "Files to upload:"
    ls -la dist/*.whl dist/*.tar.gz pyz-artifacts/*.pyz 2>/dev/null
fi

echo "Release upload initiated for $TAG_NAME"