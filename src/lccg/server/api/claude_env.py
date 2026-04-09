"""Claude environment variables API — read/write ANTHROPIC_* env vars from shell profiles."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")

# Compiled patterns for reading env vars from shell profiles
_BASE_URL_PATTERNS = [
    re.compile(r'^\s*export\s+ANTHROPIC_BASE_URL\s*=\s*[\'"]?([^\s\'"]+)', re.IGNORECASE),
    re.compile(r'^\s*ANTHROPIC_BASE_URL\s*=\s*[\'"]?([^\s\'"]+)', re.IGNORECASE),
]
_API_KEY_PATTERNS = [
    re.compile(r'^\s*export\s+ANTHROPIC_API_KEY\s*=\s*[\'"]([^\'"]+)', re.IGNORECASE),
    re.compile(r'^\s*ANTHROPIC_API_KEY\s*=\s*([^\s]+)', re.IGNORECASE),
]
# Pattern to detect existing ANTHROPIC_* lines for removal
_ANTHROPIC_LINE = re.compile(r'^\s*(export\s+)?ANTHROPIC_(BASE_URL|API_KEY)\s*=', re.IGNORECASE)


def _read_env_from_shell_profile() -> dict[str, str]:
    """Read ANTHROPIC_* vars from shell profile files on macOS/Linux."""
    vars: dict[str, str] = {}
    profile_files = [
        Path.home() / ".zshrc",
        Path.home() / ".bashrc",
        Path.home() / ".bash_profile",
        Path.home() / ".profile",
    ]

    for pf in profile_files:
        if not pf.exists():
            continue
        try:
            content = pf.read_text(encoding="utf-8")
        except Exception:
            continue

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            for p in _BASE_URL_PATTERNS:
                m = p.match(stripped)
                if m:
                    vars["ANTHROPIC_BASE_URL"] = m.group(1).strip()
                    break

            for p in _API_KEY_PATTERNS:
                m = p.match(stripped)
                if m:
                    vars["ANTHROPIC_API_KEY"] = m.group(1).strip()
                    break

    return vars


def _read_env_from_registry() -> dict[str, str]:
    """Read ANTHROPIC_* vars from Windows user environment variables."""
    vars: dict[str, str] = {}
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Environment]::GetEnvironmentVariables('User') | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            env = json.loads(result.stdout)
            for key in ["ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY"]:
                if key in env:
                    vars[key] = env[key]
    except Exception:
        pass
    return vars


def _write_env_to_shell_profile(base_url: str, api_key: str) -> tuple[bool, str]:
    """Write ANTHROPIC_* vars to shell profile. Returns (success, error)."""
    profiles = [Path.home() / ".zshrc", Path.home() / ".bashrc"]
    target: Path | None = None
    for pf in profiles:
        if pf.exists() and pf.stat().st_size > 0:
            target = pf
            break
    if not target:
        target = Path.home() / ".zshrc"

    try:
        content = target.read_text(encoding="utf-8")
    except Exception as e:
        return False, str(e)

    # Remove existing ANTHROPIC_* lines
    lines = [
        l for l in content.splitlines()
        if not _ANTHROPIC_LINE.match(l.strip())
    ]

    # Append new vars
    if lines and lines[-1].strip():
        lines.append("")
    lines.extend([
        "# LCCG Gateway",
        f"export ANTHROPIC_BASE_URL={base_url}",
        f"export ANTHROPIC_API_KEY={json.dumps(api_key)}",
        "",
    ])

    try:
        target.write_text("\n".join(lines), encoding="utf-8")
        return True, ""
    except Exception as e:
        return False, str(e)


def _write_env_to_registry(base_url: str, api_key: str) -> tuple[bool, str]:
    """Write ANTHROPIC_* vars to Windows registry. Returns (success, error)."""
    try:
        p1 = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"[Environment]::SetEnvironmentVariable('ANTHROPIC_BASE_URL', {json.dumps(base_url)}, 'User')"],
            capture_output=True, text=True, timeout=10,
        )
        p2 = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"[Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', {json.dumps(api_key)}, 'User')"],
            capture_output=True, text=True, timeout=10,
        )
        if p1.returncode == 0 and p2.returncode == 0:
            return True, ""
        return False, (p1.stderr or p1.stdout or "")[:200]
    except Exception as e:
        return False, str(e)


@router.get("/config/claude-env")
async def get_claude_env() -> dict:
    """Return current ANTHROPIC_* environment variables."""
    if platform.system() == "Windows":
        vars = _read_env_from_registry()
    else:
        vars = _read_env_from_shell_profile()

    # Also check current process environment
    for key in ["ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY"]:
        if key not in vars:
            val = os.environ.get(key)
            if val:
                vars[key] = val

    api_key = vars.get("ANTHROPIC_API_KEY", "")
    if api_key and len(api_key) > 12:
        api_key_display = f"{api_key[:8]}...{api_key[-4:]}"
    else:
        api_key_display = api_key or ""

    return {
        "base_url": vars.get("ANTHROPIC_BASE_URL", ""),
        "api_key": api_key_display,
        "api_key_raw": bool(api_key),
    }


@router.put("/config/claude-env")
async def update_claude_env(request: Request) -> JSONResponse:
    """Update ANTHROPIC_* environment variables."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    base_url = body.get("base_url", "").strip()
    api_key = body.get("api_key", "").strip()

    if platform.system() == "Windows":
        success, error = _write_env_to_registry(base_url, api_key)
    else:
        success, error = _write_env_to_shell_profile(base_url, api_key)

    if not success:
        return JSONResponse(status_code=500, content={"error": f"Failed to write env: {error}"})

    return JSONResponse(content={"status": "ok"})
