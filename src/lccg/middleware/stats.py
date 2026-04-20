"""Request/Response statistics tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class RequestRecord:
    timestamp: float
    provider: str
    model: str
    status: str  # "success" | "error"
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    scenario: str | None = None


@dataclass
class ProviderStats:
    total: int = 0
    success: int = 0
    error: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.success if self.success > 0 else 0.0


class StatsCollector:
    """Thread-safe collector for request statistics."""

    def __init__(self, max_records: int = 1000) -> None:
        self._records: list[RequestRecord] = []
        self._max = max_records
        self._lock = Lock()
        self._start_time = time.monotonic()

    def record(
        self,
        provider: str,
        model: str,
        status: str,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        error: str | None = None,
        scenario: str | None = None,
    ) -> None:
        """Record a completed request."""
        rec = RequestRecord(
            timestamp=time.time(),
            provider=provider,
            model=model,
            status=status,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error=error,
            scenario=scenario,
        )
        with self._lock:
            self._records.append(rec)
            if len(self._records) > self._max:
                self._records = self._records[-self._max :]

    def start_timer(self) -> RequestTimer:
        """Start timing a request."""
        timer = RequestTimer(self)
        timer._start = time.monotonic()
        return timer

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def get_summary(self) -> dict[str, Any]:
        """Get overall summary statistics."""
        with self._lock:
            records = list(self._records)

        total = len(records)
        success = sum(1 for r in records if r.status == "success")
        error = sum(1 for r in records if r.status == "error")
        total_input = sum(r.input_tokens for r in records)
        total_output = sum(r.output_tokens for r in records)
        total_latency = sum(r.latency_ms for r in records)

        return {
            "total_requests": total,
            "success": success,
            "error": error,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "avg_latency_ms": round(total_latency / success, 1) if success else 0,
            "uptime_seconds": round(self.uptime_seconds, 1),
        }

    def get_per_provider(self) -> dict[str, dict[str, Any]]:
        """Get per-provider statistics."""
        with self._lock:
            records = list(self._records)

        stats: dict[str, ProviderStats] = {}
        for r in records:
            if r.provider not in stats:
                stats[r.provider] = ProviderStats()
            s = stats[r.provider]
            s.total += 1
            if r.status == "success":
                s.success += 1
            else:
                s.error += 1
            s.total_input_tokens += r.input_tokens
            s.total_output_tokens += r.output_tokens
            s.total_latency_ms += r.latency_ms

        return {
            name: {
                "total": s.total,
                "success": s.success,
                "error": s.error,
                "total_input_tokens": s.total_input_tokens,
                "total_output_tokens": s.total_output_tokens,
                "avg_latency_ms": round(s.avg_latency_ms, 1),
            }
            for name, s in stats.items()
        }

    def get_recent(self, n: int = 10) -> list[dict[str, Any]]:
        """Get the most recent N request records."""
        with self._lock:
            records = self._records[-n:]

        return [
            {
                "timestamp": r.timestamp,
                "provider": r.provider,
                "model": r.model,
                "status": r.status,
                "latency_ms": round(r.latency_ms, 1),
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "scenario": r.scenario,
                "error": r.error,
            }
            for r in reversed(records)
        ]


class RequestTimer:
    """Context manager for timing a request."""

    def __init__(self, collector: StatsCollector) -> None:
        self._collector = collector
        self._start: float = 0

    def __enter__(self) -> RequestTimer:
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    @property
    def elapsed_ms(self) -> float:
        return (time.monotonic() - self._start) * 1000

    def finish(
        self,
        provider: str,
        model: str,
        status: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        error: str | None = None,
        scenario: str | None = None,
    ) -> None:
        """Record the completed request."""
        self._collector.record(
            provider=provider,
            model=model,
            status=status,
            latency_ms=self.elapsed_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error=error,
            scenario=scenario,
        )
