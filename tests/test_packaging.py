import re
from pathlib import Path

from click.testing import CliRunner

from lccg.cli.main import cli

ROOT = Path(__file__).resolve().parents[1]


def read_repo_file(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pyproject_exists():
    assert (ROOT / "pyproject.toml").exists()


def test_pyproject_metadata():
    """Verify pyproject.toml has valid metadata (name, version) and project.scripts entry."""
    content = read_repo_file("pyproject.toml")

    # Check name
    name_match = re.search(r'^name\s*=\s*"([^"]+)"', content, flags=re.MULTILINE)
    assert name_match is not None, "name not found in pyproject.toml"
    assert name_match.group(1) == "lccg", f"expected name 'lccg', got '{name_match.group(1)}'"

    # Check version
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', content, flags=re.MULTILINE)
    assert version_match is not None, "version not found in pyproject.toml"
    version = version_match.group(1)
    assert re.match(r"^\d+\.\d+\.\d+$", version), (
        f"version '{version}' does not match semver pattern"
    )

    # Check project.scripts entry
    scripts_match = re.search(r'^lccg\s*=\s*"([^"]+)"', content, flags=re.MULTILINE)
    assert scripts_match is not None, "project.scripts entry 'lccg' not found in pyproject.toml"
    assert scripts_match.group(1) == "lccg.cli.main:cli", (
        f"unexpected script target: {scripts_match.group(1)}"
    )


def test_installers_use_local_source_checkout():
    """Installers should leave users with a local repo checkout that can be updated later."""
    unix_installer = read_repo_file("install.sh")
    windows_installer = read_repo_file("install.ps1")

    assert "$HOME/.lccg/source" in unix_installer
    assert "git clone" in unix_installer
    assert "git -C" in unix_installer
    assert 'pip install -e "$SRC_DIR"' in unix_installer

    assert ".lccg\\source" in windows_installer
    assert "git clone" in windows_installer
    assert "git -C" in windows_installer
    assert "-m pip install -e" in windows_installer


def test_update_scripts_reinstall_from_source_checkout():
    unix_update = read_repo_file("tools/update.sh")
    windows_update = read_repo_file("tools/update.ps1")

    assert "git -C" in unix_update
    assert "pull --ff-only" in unix_update
    assert 'pip install -e "$SRC_DIR"' in unix_update

    assert "git -C" in windows_update
    assert "pull --ff-only" in windows_update
    assert "-m pip install -e" in windows_update


def test_install_docs_describe_repository_update_flow():
    install_doc = read_repo_file("INSTALL.md")

    assert "lccg update" in install_doc
    assert "~/.lccg/source" in install_doc
    assert "git+https://" not in install_doc


def test_cli_exposes_update_command():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "update" in result.output


def test_legacy_release_packaging_scripts_removed():
    for path in [
        "tools/install.sh",
        "tools/install.ps1",
        "tools/setup.sh",
        "tools/universal-install.sh",
        "tools/build.pyz.sh",
        "tools/upload-release.sh",
        "tools/versions.json",
    ]:
        assert not (ROOT / path).exists(), f"{path} should not be part of the update path"
