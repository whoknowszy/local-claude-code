#!/bin/bash
# tools/setup.sh - Complete setup script for all platforms

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# Function to detect OS and architecture
get_platform() {
    local os_name="$(uname -s)"
    local machine="$(uname -m)"

    case "$os_name" in
        Linux)
            case "$machine" in
                x86_64|x86_64) echo "linux-x64" ;;
                aarch64|arm64) echo "linux-arm64" ;;
                *) echo "linux-x64" ;;
            esac
            ;;
        Darwin)
            case "$machine" in
                x86_64|x86_64) echo "macos-x64" ;;
                aarch64|arm64) echo "macos-arm64" ;;
                *) echo "macos-x64" ;;
            esac
            ;;
        *)
            echo "Unsupported OS: $os_name"
            exit 1
            ;;
    esac
}

# Detect platform and download appropriate pyz
PLATFORM=$(get_platform)
PYZ_FILE="lccg-${PLATFORM}.pyz"
LATEST_VERSION="0.4.1"
BASE_URL="https://github.com/whoknowszy/local-claude-code/releases/download/v${LATEST_VERSION}"
TARGET_DIR="${LCCG_DIR:-$HOME/.local/bin}"

echo "Setting up lccg for platform: $PLATFORM"
echo "Version: $LATEST_VERSION"
echo "Target directory: $TARGET_DIR"

# Ensure target directory exists
mkdir -p "$TARGET_DIR"

# Download pyz if not exists
if [ ! -f "$TARGET_DIR/$PYZ_FILE" ]; then
    echo "Downloading $PYZ_FILE..."
    if command -v curl >/dev/null 2>&1; then
        curl -L -o "$TARGET_DIR/$PYZ_FILE" "$BASE_URL/$PYZ_FILE"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$TARGET_DIR/$PYZ_FILE" "$BASE_URL/$PYZ_FILE"
    else
        echo "Error: curl or wget is required" >&2
        exit 1
    fi
fi

# Make executable
chmod +x "$TARGET_DIR/$PYZ_FILE"

# Create symlink if not exists
if [ ! -L "$TARGET_DIR/lccg" ]; then
    ln -sf "$TARGET_DIR/$PYZ_FILE" "$TARGET_DIR/lccg"
fi

echo "Setup complete! Run 'lccg' to start the gateway."