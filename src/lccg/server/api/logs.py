"""Log streaming API endpoint for UI."""

from __future__ import annotations

import asyncio
import json
import queue

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api")


def _queue_get(q: queue.Queue, timeout: float) -> str | None:
    """Blocking read from queue. Returns None on timeout."""
    try:
        return q.get(block=True, timeout=timeout)
    except queue.Empty:
        return None


@router.get("/logs/stream")
async def stream_logs(request: Request) -> StreamingResponse:
    """SSE endpoint that streams log lines as they arrive."""
    q: queue.Queue = request.app.state.log_queue

    async def generate():
        loop = asyncio.get_running_loop()
        while True:
            if await request.is_disconnected():
                break
            # Run blocking queue.get() in a thread so it doesn't block the event
            # loop. This keeps the path compatible with Python 3.9.
            line = await loop.run_in_executor(None, _queue_get, q, 30.0)
            if line is None:
                yield b": heartbeat\n\n"
            else:
                yield f"data: {line}\n\n".encode()

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
