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