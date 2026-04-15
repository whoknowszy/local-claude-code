#!/bin/bash
# tools/install.sh - Universal installation script for lccg

set -e

LATEST_VERSION="0.4.1"
BASE_URL="https://github.com/whoknowszy/local-claude-code/releases/download/v${LATEST_VERSION}"

download_file() {
    local url="$1"
    local output="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -L -o "$output" "$url"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$output" "$url"
    else
        echo "Error: curl or wget is required" >&2
        exit 1
    fi
}

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

main() {
    local platform
    platform=$(get_platform)
    local pyz_file="lccg-${platform}.pyz"
    local target_dir="${LCCG_DIR:-$HOME/.local/bin}"

    echo "Installing lccg for platform: $platform"

    mkdir -p "$target_dir"

    echo "Downloading $pyz_file..."
    download_file "$BASE_URL/$pyz_file" "$target_dir/$pyz_file"

    chmod +x "$target_dir/$pyz_file"

    echo "Creating lccg symlink..."
    ln -sf "$target_dir/$pyz_file" "$target_dir/lccg"

    echo "Installation complete. Run 'lccg' to start the gateway."
}

main "$@"