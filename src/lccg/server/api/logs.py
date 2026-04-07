"""Log streaming API endpoint for UI."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api")


@router.get("/logs/stream")
async def stream_logs(request: Request) -> StreamingResponse:
    """SSE endpoint that streams log lines as they arrive."""
    queue: asyncio.Queue[str | None] = request.app.state.log_queue

    async def generate():
        while True:
            if await request.is_disconnected():
                break
            try:
                line = await asyncio.wait_for(queue.get(), timeout=30.0)
                if line is None:
                    break
                yield f"data: {line}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/logs/recent")
async def recent_logs(request: Request) -> list[dict]:
    """Return recent logs from the queue history (if available)."""
    history = getattr(request.app.state, "log_history", [])
    result = []
    for line in history:
        try:
            result.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            result.append({"event": line})
    return result
