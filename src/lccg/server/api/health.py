"""Health status API endpoint for UI."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")


@router.get("/health")
async def get_health(request: Request) -> JSONResponse:
    """Get health status for all providers."""
    health_tracker = request.app.state.health
    all_statuses = health_tracker.get_all_statuses()
    config = health_tracker.config

    return JSONResponse(
        content={
            "providers": all_statuses,
            "config": {
                "failure_threshold": config.failure_threshold,
                "recovery_seconds": config.recovery_seconds,
                "half_open_interval": config.half_open_interval,
                "half_open_max_requests": config.half_open_max_requests,
            },
        }
    )
