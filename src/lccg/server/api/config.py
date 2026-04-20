"""Config API endpoints for UI."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from lccg.config.loader import save_config
from lccg.config.schema import GatewayConfig
from lccg.provider.registry import ProviderRegistry
from lccg.router.engine import RouterEngine

router = APIRouter(prefix="/api")


@router.get("/config")
async def get_config(request: Request, reveal: bool = False) -> dict:
    """Return full config as JSON. API keys masked by default, use ?reveal=true to show."""
    config: GatewayConfig = request.app.state.config
    data = config.model_dump(mode="json")

    if not reveal:
        for p in data.get("providers", []):
            if p.get("api_key"):
                key = p["api_key"]
                if len(key) > 12:
                    p["api_key"] = f"{key[:8]}...{key[-4:]}"
        if data.get("server", {}).get("api_key"):
            data["server"]["api_key"] = "***"

    return data


def _providers_equal(a: list, b: list) -> bool:
    """Compare provider lists by serialized JSON (ignoring order)."""
    import json

    sa = sorted([json.dumps(p.model_dump(mode="json"), sort_keys=True) for p in a])
    sb = sorted([json.dumps(p.model_dump(mode="json"), sort_keys=True) for p in b])
    return sa == sb


@router.put("/config")
async def update_config(request: Request) -> JSONResponse:
    """Update full config. Validates, saves to YAML, hot-reloads affected subsystems."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    try:
        new_config = GatewayConfig(**body)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Validation error: {e}"})

    # Save to file
    config_path = getattr(request.app.state, "config_path", None)
    try:
        save_config(new_config, config_path)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to save config: {e}"})

    old_config: GatewayConfig = request.app.state.config
    providers_changed = not _providers_equal(old_config.providers, new_config.providers)

    if providers_changed:
        # Rebuild registry + router
        old_registry = request.app.state.registry
        try:
            new_registry = ProviderRegistry(new_config)
            new_router = RouterEngine(new_config, new_registry)
        except Exception as e:
            return JSONResponse(
                status_code=500, content={"error": f"Failed to rebuild provider registry: {e}"}
            )

        request.app.state.config = new_config
        request.app.state.registry = new_registry
        request.app.state.router = new_router

        # Close old connections in background
        import asyncio

        asyncio.create_task(old_registry.close_all())
    else:
        # Only router config changed — just rebuild router
        request.app.state.config = new_config
        request.app.state.router = RouterEngine(new_config, request.app.state.registry)

    return JSONResponse(content={"status": "ok", "providers_rebuilt": providers_changed})
