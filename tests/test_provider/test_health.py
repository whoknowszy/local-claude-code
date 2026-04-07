"""Tests for provider health tracking."""

import time

from lccg.provider.health import ProviderHealth


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
        # Wait a tiny bit for recovery
        import time
        time.sleep(0.002)
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
