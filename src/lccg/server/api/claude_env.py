"""Claude environment variables API — stores ANTHROPIC_* env vars in ~/.lccg/claude-env.json."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")


def _env_file() -> Path:
    return Path.home() / ".lccg" / "claude-env.json"


def _load() -> dict:
    f = _env_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"base_url": "http://127.0.0.1:8765", "api_key": "", "model": ""}


def _save(data: dict) -> None:
    _env_file().parent.mkdir(parents=True, exist_ok=True)
    _env_file().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@router.get("/config/claude-env")
async def get_claude_env() -> dict:
    data = _load()
    api_key = data.get("api_key", "")
    if api_key and len(api_key) > 12:
        api_key_display = f"{api_key[:8]}...{api_key[-4:]}"
    else:
        api_key_display = api_key
    return {
        "base_url": data.get("base_url", ""),
        "api_key": api_key_display,
        "model": data.get("model", ""),
        "raw": data,
    }


@router.put("/config/claude-env")
async def update_claude_env(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    data = {
        "base_url": str(body.get("base_url", "")).strip(),
        "api_key": str(body.get("api_key", "")).strip(),
        "model": str(body.get("model", "")).strip(),
    }

    try:
        _save(data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to save: {e}"})

    return JSONResponse(content={"status": "ok"})
