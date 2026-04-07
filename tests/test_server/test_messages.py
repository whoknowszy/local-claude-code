"""Tests for the server messages endpoint."""

import json

import pytest
from fastapi.testclient import TestClient

from lccg.config.schema import GatewayConfig, ProviderConfig, ProviderType
from lccg.provider.registry import ProviderRegistry
from lccg.router.engine import RouterEngine
from lccg.server.app import create_app


def _make_app(**config_kwargs) -> tuple:
    """Create a test app with given config overrides."""
    config = GatewayConfig(
        providers=[
            ProviderConfig(
                name="test-provider",
                type=ProviderType.ANTHROPIC,
                base_url="https://api.test.com/v1/messages",
                api_key="sk-test",
                models=["model-1"],
            ),
        ],
        **config_kwargs,
    )
    registry = ProviderRegistry(config)
    router = RouterEngine(config, registry)
    app = create_app(config, registry, router)
    return app, config, registry


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        app, _, _ = _make_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAuthMiddleware:
    def test_no_auth_configured(self):
        app, _, _ = _make_app()
        client = TestClient(app)
        # No api_key configured, should pass through
        response = client.post("/v1/messages", json={"model": "model-1", "max_tokens": 100, "messages": []})
        # Will fail because provider is unreachable, but should not be 401
        assert response.status_code != 401

    def test_auth_configured_wrong_key(self):
        app, _, _ = _make_app(server={"host": "127.0.0.1", "port": 8765, "api_key": "correct-key"})
        # Rebuild with server config
        config = GatewayConfig(
            providers=[
                ProviderConfig(
                    name="test-provider",
                    type=ProviderType.ANTHROPIC,
                    base_url="https://api.test.com/v1/messages",
                    api_key="sk-test",
                    models=["model-1"],
                ),
            ],
        )
        config.server.api_key = "correct-key"
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)
        app = create_app(config, registry, router)

        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={"model": "model-1", "max_tokens": 100, "messages": []},
            headers={"x-api-key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_auth_configured_correct_key(self):
        config = GatewayConfig(
            providers=[
                ProviderConfig(
                    name="test-provider",
                    type=ProviderType.ANTHROPIC,
                    base_url="https://api.test.com/v1/messages",
                    api_key="sk-test",
                    models=["model-1"],
                ),
            ],
        )
        config.server.api_key = "correct-key"
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)
        app = create_app(config, registry, router)

        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={"model": "model-1", "max_tokens": 100, "messages": []},
            headers={"x-api-key": "correct-key"},
        )
        # Provider is unreachable, but auth should pass (not 401)
        assert response.status_code != 401


class TestInvalidRequest:
    def test_invalid_json(self):
        app, _, _ = _make_app()
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_unknown_model_no_default(self):
        config = GatewayConfig(
            providers=[
                ProviderConfig(
                    name="test-provider",
                    type=ProviderType.ANTHROPIC,
                    base_url="https://api.test.com/v1/messages",
                    api_key="sk-test",
                    models=["model-1"],
                ),
            ],
        )
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)
        app = create_app(config, registry, router)

        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={"model": "unknown-model", "max_tokens": 100, "messages": []},
        )
        assert response.status_code == 400
        assert "Cannot resolve model" in response.json()["error"]["message"]
