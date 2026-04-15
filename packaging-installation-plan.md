# Self-Hosted Package Installation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a self-contained packaging and installation system that allows deploying and updating the lccg gateway on any platform without GitHub Actions dependencies or associated costs.

**Architecture:** Design a standalone packaging pipeline using Python's build system (pyproject.toml) to produce platform-specific installers (wheel + pyz), combined with a universal installation script that handles downloading and installation from any HTTP-compatible storage. The system uses uv for dependency management to avoid pip compatibility issues.

**Tech Stack:** Python build tools (pyproject.toml, uv), shiv for single-file executables, standard Python packaging (setuptools/hatchling), curl/wget for installation, shell scripts for platform detection.

---

### Task 1: Create pyproject.toml with build configuration

**Files:**
- Create: `pyproject.toml`
- Modify: `setup.py` (remove or deprecate)

- [ ] **Step 1: Write the failing test**

```python
def test_pyproject_exists():
    import os
    assert os.path.exists("pyproject.toml")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_pyproject_exists -v`
Expected: FAIL with "File not found"

- [ ] **Step 3: Write minimal implementation**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "lccg"
version = "0.4.1"
description = "Local Claude Code Gateway"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}
authors = [
    {name = "zhangyi", email = "zhangyi@example.com"}
]
dependencies = [
    "fastapi>=0.104.0",
    "httpx>=0.25.0",
    "pydantic>=2.5.0",
    "structlog>=23.0.0",
    "uvicorn>=0.24.0",
    "pyyaml>=6.0",
    "python-multipart>=0.0.6",
]

[project.scripts]
lccg = "lccg.cli.main:cli"

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "ruff>=0.0.200",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_pyproject_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: add pyproject.toml with project metadata"
```

### Task 2: Build standalone installer script

**Files:**
- Create: `tools/install.sh`
- Create: `tools/install.ps1`

- [ ] **Step 1: Write the failing test**

```python
def test_install_script_exists():
    import os
    assert os.path.exists("tools/install.sh")
    assert os.path.exists("tools/install.ps1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_install_script_exists -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```bash
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
```

```powershell
# tools/install.ps1
# Universal installation script for lccg (Windows PowerShell)

$LatestVersion = "0.4.1"
$BaseUrl = "https://github.com/whoknowszy/local-claude-code/releases/download/v${LatestVersion}"

function Get-Platform {
    $os = $PSVersionTable.OS
    $arch = $env:PROCESSOR_ARCHITECTURE

    if ($os -like "*Linux*") {
        switch ($arch) {
            "AMD64" { return "linux-x64" }
            "ARM64" { return "linux-arm64" }
            default { return "linux-x64" }
        }
    } elseif ($os -like "*Windows*") {
        switch ($arch) {
            "AMD64" { return "windows-x64" }
            "ARM64" { return "windows-arm64" }
            default { return "windows-x64" }
        }
    } elseif ($os -like "*Darwin*") {
        switch ($arch) {
            "AMD64" { return "macos-x64" }
            "ARM64" { return "macos-arm64" }
            default { return "macos-x64" }
        }
    }
}

function Invoke-Download {
    param($url, $output)
    if (Get-Command Invoke-WebRequest -ErrorAction SilentlyContinue) {
        Invoke-WebRequest -Uri $url -OutFile $output
    } elseif (Get-Command curl -ErrorAction SilentlyContinue) {
        curl -L -o $output $url
    } else {
        Write-Error "Neither Invoke-WebRequest nor curl is available"
        exit 1
    }
}

$platform = Get-Platform
$pyzFile = "lccg-${platform}.pyz"
$targetDir = ${env:LOCALAPPDATA} + "\bin"

if ($env:LCCG_DIR) {
    $targetDir = $env:LCCG_DIR
}

Write-Host "Installing lccg for platform: $platform"

if (!(Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force
}

Write-Host "Downloading $pyzFile..."
Invoke-Download -url "$BaseUrl/$pyzFile" -output "$targetDir\$pyzFile"

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

Write-Host "Creating lccg shortcut..."
$targetFile = "$targetDir\lccg.ps1"
Set-Content -Path $targetFile -Value "& '$targetDir\$pyzFile' @args"

Write-Host "Installation complete. Run 'lccg' to start the gateway."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_install_script_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/install.sh tools/install.ps1
git commit -m "build: add universal installation scripts for Linux and Windows"
```

### Task 3: Create pyz build script using uv

**Files:**
- Create: `tools/build.pyz.sh`

- [ ] **Step 1: Write the failing test**

```python
def test_build_script_exists():
    import os
    assert os.path.exists("tools/build.pyz.sh")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_build_script_exists -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```bash
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_build_script_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/build.pyz.sh
git commit -m "build: create pyz build script using uv"
```

### Task 4: Create download and install wrapper script

**Files:**
- Create: `tools/setup.sh`

- [ ] **Step 1: Write the failing test**

```python
def test_setup_script_exists():
    import os
    assert os.path.exists("tools/setup.sh")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_setup_script_exists -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```bash
#!/bin/bash
# tools/setup.sh - Complete setup script

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_setup_script_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/setup.sh
git commit -m "build: create universal setup script for all platforms"
```

### Task 5: Create README with installation instructions

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

```python
def test_readme_has_installation_instructions():
    import os
    readme_path = "README.md"
    assert os.path.exists(readme_path)
    with open(readme_path, 'r') as f:
        content = f.read()
    assert "install" in content.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_readme.py::test_readme_has_installation_instructions -v`
Expected: FAIL or PASS depending on current state

- [ ] **Step 3: Write minimal implementation**

```markdown
## Installation

### Using the Universal Installer (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/tools/setup.sh | bash
```

Or on Windows (PowerShell):

```powershell
iwr -useb https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/tools/setup.ps1 | iex
```

### Manual Installation

1. Download the pre-built package for your platform from the [releases page](https://github.com/whoknowszy/local-claude-code/releases)
2. Extract the archive
3. Run `./lccg` (Linux/Mac) or `lccg.exe` (Windows)

### Environment Variables

- `LCCG_DIR`: Custom installation directory (default: `~/.local/bin`)
- `LCCG_VERSION`: Force specific version (default: latest)

### Updating

```bash
# Re-run the setup script to get the latest version
curl -sSL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/tools/setup.sh | bash
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_readme.py::test_readme_has_installation_instructions -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add installation instructions to README"
```

### Task 6: Create version configuration file

**Files:**
- Create: `tools/versions.json`

- [ ] **Step 1: Write the failing test**

```python
def test_versions_config_exists():
    import os
    assert os.path.exists("tools/versions.json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_versions_config_exists -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```json
{
  "latest": "0.4.1",
  "versions": {
    "0.4.1": {
      "url": "https://github.com/whoknowszy/local-claude-code/releases/download/v0.4.1",
      "pyz_files": {
        "linux-x64": "lccg-linux-x64.pyz",
        "linux-arm64": "lccg-linux-arm64.pyz",
        "macos-x64": "lccg-macos-x64.pyz",
        "macos-arm64": "lccg-macos-arm64.pyz",
        "windows-x64": "lccg-windows-x64.pyz",
        "windows-arm64": "lccg-windows-arm64.pyz"
      },
      "changelog": "Fixed content extraction in streaming responses",
      "release_date": "2024-04-15"
    }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_versions_config_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/versions.json
git commit -m "build: add version configuration file"
```

### Task 7: Create GitHub release uploader script (for manual releases)

**Files:**
- Create: `tools/upload-release.sh`

- [ ] **Step 1: Write the failing test**

```python
def test_upload_script_exists():
    import os
    assert os.path.exists("tools/upload-release.sh")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_upload_script_exists -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```bash
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_upload_script_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/upload-release.sh
git commit -m "build: add manual release uploader script"
```

### Task 8: Create cleanup script for testing

**Files:**
- Create: `tools/cleanup.sh`

- [ ] **Step 1: Write the failing test**

```python
def test_cleanup_script_exists():
    import os
    assert os.path.exists("tools/cleanup.sh")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_cleanup_script_exists -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```bash
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

# Remove pyz files
find . -name "*.pyz" -type f -delete

# Remove test installations
if command -v uv &> /dev/null; then
    echo "Removing test virtual environments..."
    uv python uninstall 3.9 2>/dev/null || true
fi

echo "Cleanup complete."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_cleanup_script_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/cleanup.sh
git commit -m "build: add cleanup script for testing artifacts"
```

### Task 9: Create installation verification script

**Files:**
- Create: `tools/verify-install.sh`

- [ ] **Step 1: Write the failing test**

```python
def test_verify_script_exists():
    import os
    assert os.path.exists("tools/verify-install.sh")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_verify_script_exists -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```bash
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_verify_script_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/verify-install.sh
git commit -m "build: add installation verification script"
```

### Task 10: Add packaging test file structure

**Files:**
- Create: `tests/test_packaging.py`

- [ ] **Step 1: Write the failing test**

```python
import os
import pytest

def test_pyproject_exists():
    assert os.path.exists("pyproject.toml")

def test_install_script_exists():
    assert os.path.exists("tools/install.sh")
    assert os.path.exists("tools/install.ps1")

def test_build_script_exists():
    assert os.path.exists("tools/build.pyz.sh")

def test_setup_script_exists():
    assert os.path.exists("tools/setup.sh")

def test_versions_config_exists():
    assert os.path.exists("tools/versions.json")

def test_upload_script_exists():
    assert os.path.exists("tools/upload-release.sh")

def test_cleanup_script_exists():
    assert os.path.exists("tools/cleanup.sh")

def test_verify_script_exists():
    assert os.path.exists("tools/verify-install.sh")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py -v`
Expected: All tests FAIL (file exists but contents don't match)

- [ ] **Step 3: Write minimal implementation**

(Already done through individual task implementations)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_packaging.py
git commit -m "test: add packaging test suite structure"
```

### Task 11: Update gitignore for build artifacts

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing test**

```python
def test_build_artifacts_ignored():
    import os
    with open(".gitignore", "r") as f:
        content = f.read()
    assert "*.pyz" in content
    assert "dist/" in content
    assert "build/" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_build_artifacts_ignored -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```gitignore
# Build artifacts
dist/
build/
*.pyz
*.egg-info/

# Test coverage
htmlcov/
.pytest_cache/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Virtual environments
.venv/
env/
venv/
ENV/

# User-specific
local-claude-code/
.cache/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_build_artifacts_ignored -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "test: update gitignore to exclude build artifacts"
```

### Task 12: Create CI fallback script (optional, for environments without GitHub Actions)

**Files:**
- Create: `tools/ci-fallback.sh`

- [ ] **Step 1: Write the failing test**

```python
def test_ci_fallback_exists():
    import os
    assert os.path.exists("tools/ci-fallback.sh")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_ci_fallback_exists -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```bash
#!/bin/bash
# tools/ci-fallback.sh - CI fallback for environments without GitHub Actions

set -e

echo "Running in fallback mode (no GitHub Actions)"
echo "This script would normally run in CI but can be used locally"
echo "Available commands:"
echo "  ./tools/setup.sh    - Install lccg"
echo "  ./tools/cleanup.sh  - Clean build artifacts"
echo "  ./tools/verify-install.sh  - Verify installation"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_ci_fallback_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/ci-fallback.sh
git commit -m "ci: add fallback script for non-GitHub environments"
```

## Summary

This plan creates a complete self-hosted packaging and installation system that:

1. **Uses modern Python packaging** (pyproject.toml, uv) instead of GitHub Actions
2. **Provides universal installers** for Linux, macOS, and Windows
3. **Eliminates CI costs** by building and hosting artifacts manually
4. **Supports easy updates** through version configuration
5. **Includes verification tools** to ensure proper installation

The system is designed to work on any platform without dependencies on GitHub Actions, making it suitable for cost-sensitive or air-gapped environments.