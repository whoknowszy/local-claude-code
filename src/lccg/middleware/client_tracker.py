"""Thread-safe client tracker with heartbeat-based liveness detection."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class ClientInfo:
    """Information about a registered client session."""

    client_id: str
    pid: int
    hostname: str
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)


class ClientTracker:
    """Track active lccg code client sessions with heartbeat timeout cleanup.

    Each `lccg code` session registers itself on startup and sends periodic
    heartbeats. If a heartbeat is not received within `heartbeat_timeout`
    seconds, the client is considered stale and removed during cleanup.
    """

    def __init__(self, heartbeat_timeout: float = 90.0) -> None:
        """Initialize the tracker.

        Args:
            heartbeat_timeout: Seconds without heartbeat before a client
                is considered stale. Default 90s (clients heartbeat every 30s,
                so 3 missed heartbeats = stale).
        """
        self._clients: dict[str, ClientInfo] = {}
        self._lock = Lock()
        self._heartbeat_timeout = heartbeat_timeout

    def register(self, pid: int, hostname: str = "unknown") -> str:
        """Register a new client session.

        Args:
            pid: Process ID of the client.
            hostname: Hostname of the client machine.

        Returns:
            A unique client_id string for this session.
        """
        client_id = uuid.uuid4().hex[:16]
        info = ClientInfo(
            client_id=client_id,
            pid=pid,
            hostname=hostname,
        )
        with self._lock:
            self._clients[client_id] = info
        return client_id

    def deregister(self, client_id: str) -> bool:
        """Remove a client session.

        Args:
            client_id: The ID returned by register().

        Returns:
            True if the client was found and removed, False otherwise.
        """
        with self._lock:
            return self._clients.pop(client_id, None) is not None

    def heartbeat(self, client_id: str) -> bool:
        """Update the heartbeat timestamp for a client.

        Args:
            client_id: The ID returned by register().

        Returns:
            True if the client was found and updated, False otherwise.
        """
        with self._lock:
            info = self._clients.get(client_id)
            if info is None:
                return False
            info.last_heartbeat = time.time()
            return True

    def active_count(self) -> int:
        """Return the number of currently registered (non-stale) clients."""
        with self._lock:
            return len(self._clients)

    def list_clients(self) -> list[dict[str, Any]]:
        """List all currently registered clients.

        Returns:
            A list of dicts with client info (client_id, pid, hostname,
            connected_at, last_heartbeat).
        """
        with self._lock:
            return [
                {
                    "client_id": info.client_id,
                    "pid": info.pid,
                    "hostname": info.hostname,
                    "connected_at": info.connected_at,
                    "last_heartbeat": info.last_heartbeat,
                }
                for info in self._clients.values()
            ]

    def cleanup_stale(self) -> int:
        """Remove clients whose last heartbeat exceeds the timeout.

        Should be called periodically by the server (e.g. via lifespan
        background task or on every relevant API call).

        Returns:
            The number of stale clients that were removed.
        """
        now = time.time()
        stale_ids: list[str] = []
        with self._lock:
            for client_id, info in self._clients.items():
                if now - info.last_heartbeat > self._heartbeat_timeout:
                    stale_ids.append(client_id)
            for cid in stale_ids:
                del self._clients[cid]
        return len(stale_ids)
