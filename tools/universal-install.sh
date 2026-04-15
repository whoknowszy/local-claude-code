#!/bin/bash
# tools/universal-install.sh - Universal installer using uv
# Works on any platform with Python 3.9+ and internet access
# Usage: curl -sSL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/tools/universal-install.sh | bash

set -e

echo "=========================================="
echo "  LCCG Universal Installer"
echo "=========================================="
echo ""

# Detect platform
OS="$(uname -s)"
MACHINE="$(uname -m)"

case "$OS-$MACHINE" in
    Linux-x86_64|Linux-x86_64)
        PLATFORM="linux-x64"
        ;;
    Linux-aarch64|Linux-arm64)
        PLATFORM="linux-arm64"
        ;;
    Darwin-x86_64|Darwin-x86_64)
        PLATFORM="macos-x64"
        ;;
    Darwin-arm64|Darwin-arm64)
        PLATFORM="macos-arm64"
        ;;
    *)
        echo "⚠️  Unknown platform: $OS-$MACHINE"
        echo "   Falling back to generic Python installation"
        PLATFORM="generic"
        ;;
esac

echo "Platform: $PLATFORM"
echo ""

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "🔍 uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install using uv directly from pyproject.toml
echo "📦 Installing lccg with dependencies..."
uv pip install -e . --python $PLATFORM

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Installation successful!"
    echo ""
    echo "You can now run:"
    echo "  lccg serve    # Start the gateway"
    echo "  lccg code     # Start with Claude Code"
    echo ""
    echo "Configuration:"
    echo "  Edit ~/.lccg/config.yaml to add your API keys"
else
    echo ""
    echo "❌ Installation failed"
    echo ""
    echo "Fallback: Install via pip:"
    echo "  pip install -e ."
    exit 1
fi