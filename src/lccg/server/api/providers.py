"""Provider CRUD API endpoints for UI."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from lccg.config.loader import save_config
from lccg.config.schema import GatewayConfig, ProviderConfig
from lccg.provider.registry import ProviderRegistry
from lccg.router.engine import RouterEngine

router = APIRouter(prefix="/api")


def _mask_provider(p: dict) -> dict:
    """Mask API key in provider dict."""
    if p.get("api_key") and len(p["api_key"]) > 12:
        key = p["api_key"]
        p["api_key"] = f"{key[:8]}...{key[-4:]}"
    return p


async def _rebuild_registry(request: Request, config: GatewayConfig) -> None:
    """Save config, close old registry, rebuild registry and router."""
    config_path = getattr(request.app.state, "config_path", None)
    save_config(config, config_path)

    old_registry = request.app.state.registry
    new_registry = ProviderRegistry(config)
    new_router = RouterEngine(config, new_registry)

    request.app.state.config = config
    request.app.state.registry = new_registry
    request.app.state.router = new_router

    await old_registry.close_all()


@router.get("/providers")
async def list_providers(request: Request) -> list[dict]:
    """List all providers with masked API keys."""
    config: GatewayConfig = request.app.state.config
    return [_mask_provider(p.model_dump(mode="json")) for p in config.providers]


@router.post("/providers")
async def create_provider(request: Request) -> JSONResponse:
    """Add a new provider."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    try:
        new_provider = ProviderConfig(**body)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Validation error: {e}"})

    config: GatewayConfig = request.app.state.config

    # Check duplicate name
    if any(p.name == new_provider.name for p in config.providers):
        return JSONResponse(
            status_code=409, content={"error": f"Provider '{new_provider.name}' already exists"}
        )

    config.providers.append(new_provider)

    try:
        await _rebuild_registry(request, config)
    except Exception as e:
        config.providers.pop()  # rollback
        return JSONResponse(status_code=500, content={"error": f"Failed to create provider: {e}"})

    return JSONResponse(status_code=201, content={"status": "ok", "name": new_provider.name})


@router.put("/providers/{name}")
async def update_provider(name: str, request: Request) -> JSONResponse:
    """Update an existing provider by name."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    config: GatewayConfig = request.app.state.config
    idx = next((i for i, p in enumerate(config.providers) if p.name == name), None)
    if idx is None:
        return JSONResponse(status_code=404, content={"error": f"Provider '{name}' not found"})

    try:
        updated = ProviderConfig(**body)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Validation error: {e}"})

    old_provider = config.providers[idx]
    config.providers[idx] = updated

    try:
        await _rebuild_registry(request, config)
    except Exception as e:
        config.providers[idx] = old_provider  # rollback
        return JSONResponse(status_code=500, content={"error": f"Failed to update provider: {e}"})

    return JSONResponse(content={"status": "ok"})


@router.delete("/providers/{name}")
async def delete_provider(name: str, request: Request) -> JSONResponse:
    """Remove a provider by name."""
    config: GatewayConfig = request.app.state.config
    idx = next((i for i, p in enumerate(config.providers) if p.name == name), None)
    if idx is None:
        return JSONResponse(status_code=404, content={"error": f"Provider '{name}' not found"})

    removed = config.providers.pop(idx)

    try:
        await _rebuild_registry(request, config)
    except Exception as e:
        config.providers.insert(idx, removed)  # rollback
        return JSONResponse(status_code=500, content={"error": f"Failed to delete provider: {e}"})

    return JSONResponse(content={"status": "ok"})
