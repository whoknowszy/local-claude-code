#!/bin/bash
# tools/verify-install.sh - Verify lccg installation

set -e

# Check if lccg is in PATH
if command -v lccg &> /dev/null; then
    echo "✓ lccg found in PATH"

    # Check if it's executable
    if [ -x "$(command -v lccg)" ]; then
        echo "✓ lccg is executable"
    else
        echo "✗ lccg is not executable"
        exit 1
    fi

    # Check the version (if supported)
    if lccg --version 2>/dev/null || lccg -v 2>/dev/null; then
        echo "✓ lccg responds to version flag"
    else
        echo "  lccg doesn't support --version flag (ok)"
    fi

    echo ""
    echo "Installation verified successfully!"
    echo "You can now run: lccg"
else
    echo "✗ lccg not found in PATH"
    echo ""
    echo "Installation directories to check:"
    echo "  - \$HOME/.local/bin"
    echo "  - \$LCCG_DIR (if set)"
    echo ""
    echo "To install, run:"
    echo "  curl -sSL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/tools/setup.sh | bash"
    exit 1
fi