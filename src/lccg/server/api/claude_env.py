"""Claude settings API — reads and writes ~/.claude/settings.json directly."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")


def _settings_file() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _load() -> dict:
    f = _settings_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


@router.get("/config/claude-env")
async def get_claude_env() -> dict:
    return _load()


@router.put("/config/claude-env")
async def update_claude_env(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    f = _settings_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        f.write_text(json.dumps(body, indent=4, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to save: {e}"})

    return JSONResponse(content={"status": "ok"})
