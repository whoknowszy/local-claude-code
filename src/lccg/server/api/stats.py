"""Stats API endpoint for UI."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")


@router.get("/stats")
async def get_stats(request: Request) -> JSONResponse:
    """Get request statistics."""
    stats = request.app.state.stats
    return JSONResponse(
        content={
            "summary": stats.get_summary(),
            "providers": stats.get_per_provider(),
            "recent": stats.get_recent(20),
        }
    )
