# Universal Self-Hosted Installation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace GitHub Actions–centric release flow with a universal, self‑contained packaging and installation system so the project can be built/installed on any platform without Actions costs or pre‑built binary downloads.

**Architecture:**
- Keep `pyproject.toml` as the single source of truth.
- Add `uv` based workflows so users can install via `pip install -e .` or a universal installer script.
- Remove hard dependency on GitHub Actions for end‑users (keep Actions only as optional automation).
- Provide simple CLI‑style scripts for common operations (install, update, uninstall).
- Ensure existing install.sh/setup.sh remain as fallbacks for users preferring them.

**Tech Stack:**
- Python packaging (hatchling backend)
- uv for dependency installation and editable installs
- Shell scripts for ergonomics; POSIX‑compatible where possible
- Standard Python/Unix tooling (curl, git, bash)

---

### Task 1: Create test file verifying packaging artifacts (failing at start)

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

def test_universal_installer_exists():
    assert os.path.exists("tools/universal-install.sh")

def test_update_script_exists():
    assert os.path.exists("tools/update.sh")

def test_uninstall_script_exists():
    assert os.path.exists("tools/uninstall.sh")

def test_versions_config_exists():
    assert os.path.exists("tools/versions.json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py -v`
Expected: Tests FAIL because files may be missing or incomplete

- [ ] **Step 3: Ensure all packaging-related files exist and are valid**

Run checks (example):
```bash
python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"  # valid TOML
test -x tools/universal-install.sh
test -x tools/update.sh || echo "update.sh will be created"
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_packaging.py
git commit -m "test: add packaging test suite to verify artifacts"
```

### Task 2: Verify/create pyproject.toml metadata

**Files:**
- Modify: `pyproject.toml` (ensure metadata/scripts align)

- [ ] **Step 1: Write the failing test**

```python
def test_pyproject_has_name_and_version():
    import tomllib
    with open("pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    assert "name" in data["project"]
    assert "version" in data["project"]
```

- [ ] **Step 2: Run test to verify it fails if metadata missing**

Run: `pytest tests/test_packaging.py::test_pyproject_has_name_and_version -v`
Expected: FAIL if test added before metadata validation

- [ ] **Step 3: Ensure pyproject.toml is valid and includes install script config**

No code change required if already valid; otherwise update `pyproject.toml` to include:
- project name/version
- project.scripts `lccg = "lccg.cli.main:cli"`
- optional dependency groups if needed

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: ensure pyproject.toml metadata and scripts are valid"
```

### Task 3: Create universal installer script (uv-based)

**Files:**
- Create: `tools/universal-install.sh`

- [ ] **Step 1: Write the failing test**

```python
def test_universal_installer_is_executable():
    import os
    assert os.access("tools/universal-install.sh", os.X_OK)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_universal_installer_is_executable -v`
Expected: FAIL before creation

- [ ] **Step 3: Write minimal implementation**

```bash
#!/bin/bash
# tools/universal-install.sh - Universal installer using uv
# Usage: curl -sSL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/tools/universal-install.sh | bash

set -e
echo "🔍 Checking for uv..."
if ! command -v uv &>/dev/null; then
  echo "uv not found, installing via cargo or official installer..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$PATH"
fi
echo "📦 Installing lccg in editable mode via uv..."
uv pip install -e . --python "$(uname -s | tr '[:upper:]' '[:lower]')-$(uname -m | sed 's/x86_64/x64/;s/aarch64/arm64/')"
echo "✅ Installation complete. Run 'lccg serve' to start the gateway."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_universal_installer_is_executable -v`
Expected: PASS after creation

- [ ] **Step 5: Commit**

```bash
git add tools/universal-install.sh
git commit -m "build: add universal installer using uv"
```

### Task 4: Create update and uninstall helpers

**Files:**
- Create: `tools/update.sh`
- Create: `tools/uninstall.sh`

- [ ] **Step 1: Write failing tests**

```python
def test_update_script_exists():
    assert os.path.exists("tools/update.sh")

def test_uninstall_script_exists():
    assert os.path.exists("tools/uninstall.sh")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_packaging.py -k "update or uninstall" -v`
Expected: FAIL before creation

- [ ] **Step 3: Write minimal implementations**

```bash
#!/bin/bash
# tools/update.sh - Update lccg to latest main
set -e
echo "🔄 Pulling latest changes..."
git pull origin main
echo "📦 Reinstalling..."
bash tools/universal-install.sh
echo "✅ Update complete."
```

```bash
#!/bin/bash
# tools/uninstall.sh - Uninstall lccg
set -e
echo "🗑️  Removing lccg package..."
uv pip uninstall lccg -y 2>/dev/null || pip uninstall lccg -y 2>/dev/null || true
echo "✅ Uninstall complete."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_packaging.py -k "update or uninstall" -v`
Expected: PASS after creation

- [ ] **Step 5: Commit**

```bash
git add tools/update.sh tools/uninstall.sh
git commit -m "build: add update and uninstall helper scripts"
```

### Task 5: Update .gitignore for build artifacts

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing test**

```python
def test_gitignore_excludes_build_artifacts():
    with open(".gitignore", "r") as f:
        content = f.read()
    assert "*.pyz" in content
    assert "dist/" in content
    assert "build/" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_gitignore_excludes_build_artifacts -v`
Expected: FAIL if patterns missing

- [ ] **Step 3: Add missing patterns**

Append to `.gitignore`:
```
# Build artifacts
dist/
build/
*.pyz
*.egg-info/

# Test/venv
.venv/
env/
venv/

# OS files
.DS_Store
Thumbs.db
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_gitignore_excludes_build_artifacts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "test: update .gitignore to exclude build artifacts"
```

### Task 6: Update documentation (INSTALL.md)

**Files:**
- Modify: `INSTALL.md`

- [ ] **Step 1: Write failing test**

```python
def test_installation_docs_mention_universal_install():
    with open("INSTALL.md", "r") as f:
        content = f.read()
    assert "universal-install.sh" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packaging.py::test_installation_docs_mention_universal_install -v`
Expected: FAIL before docs update

- [ ] **Step 3: Update INSTALL.md with new flow**

Add a clear section:
## Universal Installation (Recommended)
```bash
curl -sSL https://raw.githubusercontent.com/whoknowszy/local-claude-code/main/tools/universal-install.sh | bash
```
Also mention standard `pip install -e .` and preserve existing `install.sh` instructions.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packaging.py::test_installation_docs_mention_universal_install -v`
Expected: PASS after update

- [ ] **Step 5: Commit**

```bash
git add INSTALL.md
git commit -m "docs: update INSTALL.md with universal installation flow"
```

### Task 7: Verify end-to-end (manual validation)

- [ ] **Step 1: Verify scripts are executable**

Run: `test -x tools/universal-install.sh && test -x tools/update.sh && test -x tools/uninstall.sh && echo "All scripts executable"`

- [ ] **Step 2: Dry-run install in a safe check**

Check syntax only:
```bash
bash -n tools/universal-install.sh && echo "Syntax OK"
```

- [ ] **Step 3: Confirm tests pass**

Run: `pytest tests/test_packaging.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit verification note**

```bash
git add -A
git commit -m "verification: confirm packaging scripts are valid and tests pass"
```

## Summary

This plan delivers a self‑hosted installation workflow:
- `universal-install.sh` uses `uv` for a consistent, cross‑platform install
- `update.sh` / `uninstall.sh` provide lifecycle management
- `.gitignore` excludes build artifacts
- Tests ensure packaging artifacts remain valid and documented
- Existing `install.sh` remains as a fallback for users preferring platform‑specific flows