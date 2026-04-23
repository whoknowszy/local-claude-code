"""Client registration API for tracking lccg code sessions."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/v1/clients", tags=["clients"])


class RegisterRequest(BaseModel):
    """Request to register a new client."""

    pid: int
    hostname: str = "unknown"


class RegisterResponse(BaseModel):
    """Response with client registration details."""

    client_id: str
    registered_at: float


class CountResponse(BaseModel):
    """Response with active client count."""

    count: int


class HeartbeatResponse(BaseModel):
    """Response from heartbeat update."""

    success: bool
    timestamp: float


@router.post("/register", response_model=RegisterResponse)
async def register_client(request: Request, body: RegisterRequest) -> dict[str, Any]:
    """Register a new client session.

    Returns a unique client_id that should be used for subsequent
    heartbeat and deregister calls.
    """
    tracker = request.app.state.client_tracker
    client_id = tracker.register(pid=body.pid, hostname=body.hostname)
    return {
        "client_id": client_id,
        "registered_at": time.time(),
    }


@router.post("/{client_id}/deregister")
async def deregister_client(request: Request, client_id: str) -> dict[str, bool]:
    """Deregister a client session.

    Removes the client from the tracker. Returns success=True if the
    client was found and removed, success=False if not found.
    """
    tracker = request.app.state.client_tracker
    success = tracker.deregister(client_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
    return {"success": True}


@router.post("/{client_id}/heartbeat", response_model=HeartbeatResponse)
async def client_heartbeat(request: Request, client_id: str) -> dict[str, Any]:
    """Update the heartbeat timestamp for a client.

    Should be called periodically (e.g., every 30 seconds) to keep
    the client session alive.
    """
    tracker = request.app.state.client_tracker
    success = tracker.heartbeat(client_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
    return {
        "success": True,
        "timestamp": time.time(),
    }


@router.get("/count", response_model=CountResponse)
async def get_client_count(request: Request) -> dict[str, int]:
    """Get the number of currently registered (non-stale) clients."""
    tracker = request.app.state.client_tracker
    return {"count": tracker.active_count()}


@router.post("/cleanup")
async def cleanup_stale_clients(request: Request) -> dict[str, int]:
    """Manually trigger cleanup of stale clients.

    Removes clients whose last heartbeat exceeds the timeout.
    Normally called automatically by the server.
    """
    tracker = request.app.state.client_tracker
    removed = tracker.cleanup_stale()
    return {"removed": removed}


@router.get("")
async def list_clients(request: Request) -> dict[str, list[dict[str, Any]]]:
    """List all currently registered clients."""
    tracker = request.app.state.client_tracker
    return {"clients": tracker.list_clients()}
