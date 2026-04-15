import os
import re
import pytest


def test_pyproject_exists():
    assert os.path.exists("pyproject.toml")


def test_pyproject_metadata():
    """Verify pyproject.toml has valid metadata (name, version) and project.scripts entry."""
    content = open("pyproject.toml").read()

    # Check name
    name_match = re.search(r'^name\s*=\s*"([^"]+)"', content, flags=re.MULTILINE)
    assert name_match is not None, "name not found in pyproject.toml"
    assert name_match.group(1) == "lccg", f"expected name 'lccg', got '{name_match.group(1)}'"

    # Check version
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', content, flags=re.MULTILINE)
    assert version_match is not None, "version not found in pyproject.toml"
    version = version_match.group(1)
    assert re.match(r"^\d+\.\d+\.\d+$", version), f"version '{version}' does not match semver pattern"

    # Check project.scripts entry
    scripts_match = re.search(r'^lccg\s*=\s*"([^"]+)"', content, flags=re.MULTILINE)
    assert scripts_match is not None, "project.scripts entry 'lccg' not found in pyproject.toml"
    assert scripts_match.group(1) == "lccg.cli.main:cli", f"unexpected script target: {scripts_match.group(1)}"