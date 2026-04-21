"""Tests for provider health tracking."""

import time

from lccg.config.schema import DegradationConfig
from lccg.provider.health import HealthStatus, ProviderHealth


class TestProviderHealth:
    def test_initially_healthy(self):
        health = ProviderHealth()
        assert health.is_healthy("test-provider") is True

    def test_failure_tracking(self):
        health = ProviderHealth(failure_threshold=3)
        health.record_failure("test-provider")
        assert health.is_healthy("test-provider") is True
        health.record_failure("test-provider")
        assert health.is_healthy("test-provider") is True
        health.record_failure("test-provider")
        assert health.is_healthy("test-provider") is False

    def test_unhealthy_after_threshold(self):
        health = ProviderHealth(failure_threshold=2)
        health.record_failure("p1")
        health.record_failure("p1")
        assert health.is_healthy("p1") is False
        # Other provider still healthy
        assert health.is_healthy("p2") is True

    def test_recovery_after_timeout(self):
        health = ProviderHealth(failure_threshold=2, recovery_seconds=0.001)
        health.record_failure("p")
        health.record_failure("p")
        assert health.is_healthy("p") is False
        # Wait a tiny bit for recovery (now enters half-open, allows probe)
        time.sleep(0.005)
        assert health.is_healthy("p") is True

    def test_success_resets(self):
        health = ProviderHealth(failure_threshold=3)
        health.record_failure("p")
        health.record_failure("p")
        health.record_success("p")
        assert health.is_healthy("p") is True
        # Can tolerate 2 more failures before unhealthy
        health.record_failure("p")
        health.record_failure("p")
        assert health.is_healthy("p") is True


class TestHalfOpenRecovery:
    """Test half-open state transitions and probe request quota."""

    def test_enters_recovering_after_recovery_seconds(self):
        health = ProviderHealth(
            DegradationConfig(failure_threshold=2, recovery_seconds=0.05, half_open_max_requests=1)
        )
        health.record_failure("p")
        health.record_failure("p")
        assert health.is_healthy("p") is False  # degraded

        time.sleep(0.1)
        status = health.get_status("p")
        assert status["status"] == HealthStatus.RECOVERING.value
        assert health.is_healthy("p") is True  # probe allowed

    def test_probe_quota_enforced(self):
        health = ProviderHealth(
            DegradationConfig(
                failure_threshold=2,
                recovery_seconds=0.05,
                half_open_interval=999,  # never resets within test
                half_open_max_requests=1,
            )
        )
        health.record_failure("p")
        health.record_failure("p")
        time.sleep(0.1)

        assert health.is_healthy("p") is True   # first probe allowed
        assert health.is_healthy("p") is False  # quota exhausted

    def test_probe_quota_resets_after_interval(self):
        health = ProviderHealth(
            DegradationConfig(
                failure_threshold=2,
                recovery_seconds=0.05,
                half_open_interval=0.1,
                half_open_max_requests=1,
            )
        )
        health.record_failure("p")
        health.record_failure("p")
        time.sleep(0.1)

        assert health.is_healthy("p") is True   # probe allowed
        assert health.is_healthy("p") is False  # quota exhausted

        time.sleep(0.15)  # wait for half_open_interval to elapse
        assert health.is_healthy("p") is True   # quota reset

    def test_probe_success_fully_recovers(self):
        health = ProviderHealth(
            DegradationConfig(failure_threshold=2, recovery_seconds=0.05)
        )
        health.record_failure("p")
        health.record_failure("p")
        time.sleep(0.1)

        health.is_healthy("p")        # probe allowed
        health.record_success("p")    # probe succeeded
        assert health.is_healthy("p") is True
        assert health.get_status("p")["status"] == HealthStatus.HEALTHY.value

    def test_probe_failure_re_degrades(self):
        health = ProviderHealth(
            DegradationConfig(failure_threshold=2, recovery_seconds=0.05)
        )
        health.record_failure("p")
        health.record_failure("p")
        time.sleep(0.1)

        health.is_healthy("p")        # probe allowed
        health.record_failure("p")    # probe failed
        assert health.get_status("p")["status"] == HealthStatus.DEGRADED.value
        assert health.is_healthy("p") is False


class TestHealthStatus:
    """Test status reporting fields."""

    def test_degraded_status_has_recovery_at(self):
        health = ProviderHealth(DegradationConfig(failure_threshold=2, recovery_seconds=60))
        health.record_failure("p")
        health.record_failure("p")
        status = health.get_status("p")
        assert status["status"] == "degraded"
        assert "recovery_at" in status

    def test_recovering_status_has_probes_remaining(self):
        health = ProviderHealth(
            DegradationConfig(failure_threshold=2, recovery_seconds=0.05, half_open_max_requests=2)
        )
        health.record_failure("p")
        health.record_failure("p")
        time.sleep(0.1)
        status = health.get_status("p")
        assert status["status"] == "recovering"
        assert status["probes_remaining"] == 2

    def test_all_statuses(self):
        health = ProviderHealth(DegradationConfig(failure_threshold=2))
        health.record_failure("a")
        health.record_failure("b")
        health.record_failure("b")
        all_st = health.get_all_statuses()
        assert "a" in all_st
        assert "b" in all_st
        assert all_st["a"]["consecutive_failures"] == 1
        assert all_st["b"]["consecutive_failures"] == 2


class TestDegradationConfig:
    """Test DegradationConfig defaults and custom values."""

    def test_default_config(self):
        health = ProviderHealth()
        assert health.config.failure_threshold == 3
        assert health.config.recovery_seconds == 60
        assert health.config.half_open_interval == 30
        assert health.config.half_open_max_requests == 1

    def test_explicit_config(self):
        config = DegradationConfig(
            failure_threshold=5, recovery_seconds=120,
            half_open_interval=60, half_open_max_requests=3,
        )
        health = ProviderHealth(config)
        assert health.config.failure_threshold == 5
        assert health.config.recovery_seconds == 120
