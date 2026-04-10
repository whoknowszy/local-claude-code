"""Provider health tracking with circuit-breaker-like behavior."""

from __future__ import annotations

import time

import structlog

logger = structlog.get_logger()


class ProviderHealth:
    """Track provider health status.

    A provider becomes unhealthy after consecutive failures exceed the threshold.
    It recovers automatically after a timeout period.
    """

    def __init__(self, failure_threshold: int = 3, recovery_seconds: int = 60) -> None:
        self._failures: dict[str, int] = {}
        self._last_failure_time: dict[str, float] = {}
        self._threshold = failure_threshold
        self._recovery = recovery_seconds

    def is_healthy(self, provider_name: str) -> bool:
        """Check if provider is healthy."""
        failures = self._failures.get(provider_name, 0)
        if failures < self._threshold:
            return True

        # Check if recovery time has passed
        last_time = self._last_failure_time.get(provider_name, 0)
        if time.monotonic() - last_time > self._recovery:
            # Auto-recover
            self._failures[provider_name] = 0
            return True

        return False

    def record_failure(self, provider_name: str) -> None:
        """Record a failure for the provider."""
        self._failures[provider_name] = self._failures.get(provider_name, 0) + 1
        self._last_failure_time[provider_name] = time.monotonic()
        failures = self._failures[provider_name]
        if failures == self._threshold:
            logger.warning(
                "provider_health.degraded",
                provider=provider_name,
                failures=failures,
                threshold=self._threshold,
                next_recovery_in_s=self._recovery,
            )

    def record_success(self, provider_name: str) -> None:
        """Reset failure count on success."""
        was_unhealthy = self._failures.get(provider_name, 0) >= self._threshold
        self._failures[provider_name] = 0
        if was_unhealthy:
            logger.info(
                "provider_health.recovered",
                provider=provider_name,
            )
