"""Provider health tracking with circuit-breaker-like behavior and half-open recovery."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

import structlog

from lccg.config.schema import DegradationConfig

logger = structlog.get_logger()


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RECOVERING = "recovering"


class ProviderHealth:
    """Track provider health status with configurable degradation and half-open recovery.

    States per provider:
    - healthy: normal operation
    - degraded: circuit open, all requests blocked
    - recovering: half-open, limited probe requests allowed

    Transition logic:
    - healthy -> degraded: consecutive failures >= failure_threshold
    - degraded -> recovering: after recovery_seconds elapsed
    - recovering -> healthy: a probe request succeeds
    - recovering -> degraded: a probe request fails (resets recovery timer)
    """

    def __init__(
        self,
        config: DegradationConfig | None = None,
        *,
        failure_threshold: int | None = None,
        recovery_seconds: int | None = None,
    ) -> None:
        """Initialize with a DegradationConfig or legacy int params for backward compat."""
        if config is not None:
            self._config = config
        else:
            self._config = DegradationConfig(
                failure_threshold=failure_threshold or 3,
                recovery_seconds=recovery_seconds or 60,
            )

        self._failures: dict[str, int] = {}
        self._last_failure_time: dict[str, float] = {}
        self._degraded_at: dict[str, float] = {}
        self._half_open_probes: dict[str, int] = {}
        self._half_open_since: dict[str, float] = {}

    def _get_state(self, provider_name: str) -> HealthStatus:
        """Determine the current state of a provider."""
        failures = self._failures.get(provider_name, 0)
        if failures < self._config.failure_threshold:
            return HealthStatus.HEALTHY

        # Check if we should transition to recovering
        degraded_at = self._degraded_at.get(provider_name, 0)
        elapsed = time.monotonic() - degraded_at
        if elapsed >= self._config.recovery_seconds:
            return HealthStatus.RECOVERING

        return HealthStatus.DEGRADED

    def is_healthy(self, provider_name: str) -> bool:
        """Check if provider is healthy (or allows a probe request in recovering state)."""
        state = self._get_state(provider_name)

        if state == HealthStatus.HEALTHY:
            return True

        if state == HealthStatus.RECOVERING:
            # Check probe quota for this half-open interval
            since = self._half_open_since.get(provider_name, 0)
            probes = self._half_open_probes.get(provider_name, 0)

            # Reset probe count if interval has elapsed
            if time.monotonic() - since >= self._config.half_open_interval:
                self._half_open_probes[provider_name] = 0
                self._half_open_since[provider_name] = time.monotonic()
                probes = 0

            if probes < self._config.half_open_max_requests:
                # Allow this probe request
                self._half_open_probes[provider_name] = probes + 1
                return True

            # Probe quota exhausted for this interval
            return False

        # DEGRADED
        return False

    def record_failure(self, provider_name: str) -> None:
        """Record a failure for the provider."""
        self._failures[provider_name] = self._failures.get(provider_name, 0) + 1
        self._last_failure_time[provider_name] = time.monotonic()
        failures = self._failures[provider_name]

        if failures == self._config.failure_threshold:
            # Transition to degraded
            self._degraded_at[provider_name] = time.monotonic()
            self._half_open_probes[provider_name] = 0
            self._half_open_since[provider_name] = 0
            logger.warning(
                "provider_health.degraded",
                provider=provider_name,
                failures=failures,
                threshold=self._config.failure_threshold,
                recovery_in_s=self._config.recovery_seconds,
            )
        elif self._get_state(provider_name) == HealthStatus.RECOVERING:
            # Probe failed in half-open -> re-degrade
            self._degraded_at[provider_name] = time.monotonic()
            self._half_open_probes[provider_name] = 0
            self._half_open_since[provider_name] = 0
            logger.warning(
                "provider_health.probe_failed",
                provider=provider_name,
                recovery_in_s=self._config.recovery_seconds,
            )

    def record_success(self, provider_name: str) -> None:
        """Reset failure count on success."""
        was_degraded = self._failures.get(provider_name, 0) >= self._config.failure_threshold
        self._failures[provider_name] = 0
        self._half_open_probes.pop(provider_name, None)
        self._half_open_since.pop(provider_name, None)
        if was_degraded:
            logger.info("provider_health.recovered", provider=provider_name)

    def get_status(self, provider_name: str) -> dict[str, Any]:
        """Get detailed health status for a single provider."""
        state = self._get_state(provider_name)
        failures = self._failures.get(provider_name, 0)
        last_failure = self._last_failure_time.get(provider_name)
        degraded_at = self._degraded_at.get(provider_name)

        result: dict[str, Any] = {
            "status": state.value,
            "consecutive_failures": failures,
            "last_failure_time": last_failure,
            "degraded_at": degraded_at,
        }

        if state == HealthStatus.RECOVERING:
            recovery_time = degraded_at + self._config.recovery_seconds if degraded_at else None
            result["recovery_at"] = recovery_time
            result["probes_remaining"] = max(
                0,
                self._config.half_open_max_requests - self._half_open_probes.get(provider_name, 0),
            )
        elif state == HealthStatus.DEGRADED and degraded_at:
            result["recovery_at"] = degraded_at + self._config.recovery_seconds

        return result

    def get_all_statuses(self) -> dict[str, dict[str, Any]]:
        """Get health status for all tracked providers."""
        all_providers = set(self._failures.keys())
        return {p: self.get_status(p) for p in all_providers}

    @property
    def config(self) -> DegradationConfig:
        """Expose current degradation config."""
        return self._config
