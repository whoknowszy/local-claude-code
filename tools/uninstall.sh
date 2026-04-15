#!/bin/bash
# tools/uninstall.sh - Uninstall lccg

echo "Uninstalling lccg..."

# Remove the package
uv pip uninstall lccg 2>/dev/null || pip uninstall lccg -y 2>/dev/null || true

# Remove configuration
rm -rf ~/.lccg

# Remove from PATH if added (not typically done automatically)
echo "✅ lccg has been uninstalled"
echo ""
echo "Note: If you added ~/.local/bin to your PATH, you may want to remove it manually"