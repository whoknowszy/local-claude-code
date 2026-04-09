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


def _read_env_from_shell_profile() -> dict[str, str]:
    """Read ANTHROPIC_* vars from shell profile files on macOS/Linux."""
    vars: dict[str, str] = {}
    patterns: list[tuple[str, re.Pattern]] = [
        # key="value" or key='value' or key=value
        (r'export\s+ANTHROPIC_BASE_URL\s*=\s*["\'"]?([^"\'\s]+)["\'"]?', re.IGNORECASE),
        (r'export\s+ANTHROPIC_API_KEY\s*=\s*["\']([^"\']+)["\']?', re.IGNORECASE),
        (r'ANTHROPIC_BASE_URL\s*=\s*["\'"]?([^"\'\s]+)["\'"]?', re.IGNORECASE),
        (r'ANTHROPIC_API_KEY\s*=\s*["\']([^"\']+)["\']?', re.IGNORECASE),
        # Without export prefix (less common)
        (r'ANTHROPIC_API_KEY\s*=\s*([^\s]+)', re.IGNORECASE),
        (r'ANTHROPIC_BASE_URL\s*=\s*([^\s]+)', re.IGNORECASE),
    ]

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
            line = line.strip()
            # Only consider lines with export or direct assignment
            for pattern in patterns:
                m = re.match(pattern[1], line, re.IGNORECASE)
                if m:
                    value = m.group(1).strip()
                    if "BASE_URL" in pattern[1].upper():
                        vars["ANTHROPIC_BASE_URL"] = value
                    elif "API_KEY" in pattern[1].upper():
                        vars["ANTHROPIC_API_KEY"] = value
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


def _write_env_to_shell_profile(base_url: str, api_key: str) -> dict:
    """Write ANTHROPIC_* vars to shell profile. Returns (success, profile_used, error)."""
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
        return False, str(target), str(e)

    # Remove existing ANTHROPIC_* lines
    lines = [l for l in content.splitlines()
             if not re.match(r'\s*(export\s+)?ANTHROPIC_(BASE_URL|API_KEY)\s*=', l, re.IGNORECASE)]

    # Append new vars
    marker = "\n# LCCG Gateway\n"
    if lines and lines[-1].strip():
        lines.append("")
    lines.extend([
        f"{marker}export ANTHROPIC_BASE_URL={base_url}",
        f"export ANTHROPIC_API_KEY={json.dumps(api_key)}",
    ])

    try:
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True, str(target), ""
    except Exception as e:
        return False, str(target), str(e)


def _write_env_to_registry(base_url: str, api_key: str) -> dict:
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
async def get_claude_env(request: Request) -> dict:
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

    # Mask API key in response
    api_key = vars.get("ANTHROPIC_API_KEY", "")
    if api_key and len(api_key) > 12:
        api_key_display = f"{api_key[:8]}...{api_key[-4:]}"
    else:
        api_key_display = api_key or ""

    return {
        "base_url": vars.get("ANTHROPIC_BASE_URL", ""),
        "api_key": api_key_display,
        "api_key_raw": bool(vars.get("ANTHROPIC_API_KEY")),
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
        success, target, error = _write_env_to_shell_profile(base_url, api_key)

    if not success:
        return JSONResponse(status_code=500, content={"error": f"Failed to write env: {error}"})

    return JSONResponse(content={"status": "ok"})
