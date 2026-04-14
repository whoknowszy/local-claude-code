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


class TestErrorResponseFormat:
    """Tests for Anthropic-compliant error response format."""

    def test_error_response_format(self):
        """Verify error responses contain Anthropic-spec format."""
        # Configure app with API key to trigger auth error
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
        # Send request with wrong API key to trigger authentication error
        response = client.post(
            "/v1/messages",
            json={"model": "model-1", "max_tokens": 100, "messages": []},
            headers={"x-api-key": "wrong-key"},
        )

        assert response.status_code == 401
        data = response.json()
        # Verify top-level "type": "error"
        assert data.get("type") == "error"
        # Verify error.type and error.message fields
        assert "error" in data
        assert "type" in data["error"]
        assert data["error"]["type"] == "authentication_error"
        assert "message" in data["error"]
        # Verify request_id field
        assert "request_id" in data


class TestProviderErrorHandling:
    """Tests for provider error handling and fallback behavior."""

    def test_rate_limit_returns_429(self):
        """Mock provider returning 429 Rate Limit."""
        from unittest.mock import AsyncMock, patch
        import httpx
        from lccg.provider.base import ProviderHTTPError

        app, config, registry = _make_app()
        client = TestClient(app)

        # Mock provider's send_request to raise ProviderHTTPError with 429
        with patch.object(
            registry.get_provider("test-provider"),
            "send_request",
            new=AsyncMock(
                side_effect=ProviderHTTPError(
                    status_code=429,
                    body='{"error": {"type": "rate_limit_error", "message": "Rate limit exceeded"}}',
                    headers={"retry-after": "30"},
                )
            ),
        ):
            response = client.post(
                "/v1/messages",
                json={"model": "model-1", "max_tokens": 100, "messages": []},
            )

        # Verify HTTP 429 status code
        assert response.status_code == 429
        data = response.json()
        # Verify error.type is rate_limit_error
        assert data["type"] == "error"
        assert data["error"]["type"] == "rate_limit_error"
        # Verify retry-after header
        assert "retry-after" in response.headers

    def test_timeout_returns_504(self):
        """Mock provider timeout returns 504."""
        from unittest.mock import AsyncMock, patch
        import httpx

        app, config, registry = _make_app()
        client = TestClient(app)

        # Mock provider's send_request to raise ReadTimeout
        with patch.object(
            registry.get_provider("test-provider"),
            "send_request",
            new=AsyncMock(side_effect=httpx.ReadTimeout("Connection timed out")),
        ):
            response = client.post(
                "/v1/messages",
                json={"model": "model-1", "max_tokens": 100, "messages": []},
            )

        # Verify HTTP 504 status code
        assert response.status_code == 504
        data = response.json()
        # Verify response body format is correct
        assert data["type"] == "error"
        assert data["error"]["type"] == "timeout_error"
        assert "request_id" in data

    def test_4xx_no_fallback(self):
        """Verify 4XX errors do not trigger fallback."""
        from unittest.mock import AsyncMock, patch, MagicMock
        from lccg.provider.base import ProviderHTTPError

        # Configure with fallback - use explicit provider prefix to ensure routing
        config = GatewayConfig(
            providers=[
                ProviderConfig(
                    name="main-provider",
                    type=ProviderType.ANTHROPIC,
                    base_url="https://api.main.com/v1/messages",
                    api_key="sk-main",
                    models=["main-model"],
                ),
                ProviderConfig(
                    name="fallback-provider",
                    type=ProviderType.ANTHROPIC,
                    base_url="https://api.fallback.com/v1/messages",
                    api_key="sk-fallback",
                    models=["fallback-model"],
                ),
            ],
            router={"default": "main-provider,main-model", "fallback": "fallback-provider,fallback-model"},
        )
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)
        app = create_app(config, registry, router)
        client = TestClient(app)

        main_provider = registry.get_provider("main-provider")
        fallback_provider = registry.get_provider("fallback-provider")

        # Mock main provider to raise 400 error
        main_mock = AsyncMock(
            side_effect=ProviderHTTPError(status_code=400, body="bad request")
        )
        fallback_mock = AsyncMock()

        with patch.object(main_provider, "send_request", main_mock):
            with patch.object(fallback_provider, "send_request", fallback_mock):
                response = client.post(
                    "/v1/messages",
                    # Use explicit provider prefix to ensure main-provider is used
                    json={"model": "main-provider/main-model", "max_tokens": 100, "messages": []},
                )

        # Verify returns 400, not fallback
        assert response.status_code == 400
        # Verify fallback provider's send_request was NOT called
        fallback_mock.assert_not_called()

    def test_5xx_triggers_fallback(self):
        """Verify 5XX errors trigger fallback."""
        from unittest.mock import AsyncMock, patch, MagicMock
        import httpx
        from lccg.provider.base import ProviderHTTPError

        # Configure with fallback - use explicit provider prefix to ensure routing
        config = GatewayConfig(
            providers=[
                ProviderConfig(
                    name="main-provider",
                    type=ProviderType.ANTHROPIC,
                    base_url="https://api.main.com/v1/messages",
                    api_key="sk-main",
                    models=["main-model"],
                ),
                ProviderConfig(
                    name="fallback-provider",
                    type=ProviderType.ANTHROPIC,
                    base_url="https://api.fallback.com/v1/messages",
                    api_key="sk-fallback",
                    models=["fallback-model"],
                ),
            ],
            router={"default": "main-provider,main-model", "fallback": "fallback-provider,fallback-model"},
        )
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)
        app = create_app(config, registry, router)
        client = TestClient(app)

        main_provider = registry.get_provider("main-provider")
        fallback_provider = registry.get_provider("fallback-provider")

        # Mock main provider to raise 500 error
        main_mock = AsyncMock(
            side_effect=ProviderHTTPError(status_code=500, body="internal error")
        )

        # Create mock response for fallback provider
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello from fallback"}],
            "model": "fallback-model",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        fallback_mock = AsyncMock(return_value=mock_response)

        with patch.object(main_provider, "send_request", main_mock):
            with patch.object(fallback_provider, "send_request", fallback_mock):
                response = client.post(
                    "/v1/messages",
                    # Use explicit provider prefix to ensure main-provider is used first
                    json={"model": "main-provider/main-model", "max_tokens": 100, "messages": []},
                )

        # Verify response is successful (from fallback provider)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "message"
        assert data["content"][0]["text"] == "Hello from fallback"
        # Verify fallback provider was called
        fallback_mock.assert_called_once()
