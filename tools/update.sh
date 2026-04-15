#!/bin/bash
# tools/update.sh - Update lccg to latest version

echo "🔄 Updating lccg..."

# Pull latest changes
git pull origin main

# Rebuild if needed
if [ -f "pyproject.toml" ]; then
    echo "📦 Checking for dependency updates..."
    uv pip install -e . --upgrade
fi

# Reinstall with universal installer
echo "📦 Reinstalling with latest version..."
bash tools/universal-install.sh

echo ""
echo "✅ Update complete!"
echo ""
echo "You can now run:"
echo "  lccg serve    # Start the gateway"
echo "  lccg code     # Start with Claude Code"