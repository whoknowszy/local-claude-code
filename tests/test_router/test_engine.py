"""Tests for the router engine."""

import pytest

from lccg.config.schema import GatewayConfig, ProviderConfig, ProviderType, RouterConfig
from lccg.provider.registry import ProviderRegistry
from lccg.router.engine import RouterEngine


def _make_config(**router_kwargs) -> GatewayConfig:
    """Create a test config with a single anthropic provider."""
    return GatewayConfig(
        providers=[
            ProviderConfig(
                name="test-provider",
                type=ProviderType.ANTHROPIC,
                base_url="https://api.test.com/v1/messages",
                api_key="sk-test",
                models=["model-1", "model-2"],
            ),
            ProviderConfig(
                name="other-provider",
                type=ProviderType.ANTHROPIC,
                base_url="https://api.other.com/v1/messages",
                api_key="sk-other",
                models=["other-model"],
            ),
        ],
        router=RouterConfig(**router_kwargs),
    )


class TestRouterEngine:
    def test_resolve_by_model_name(self):
        config = _make_config(default="test-provider,model-1")
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        result = router.resolve({"model": "model-1"})
        assert result.provider_name == "test-provider"
        assert result.model == "model-1"

    def test_resolve_with_provider_prefix(self):
        config = _make_config(default="test-provider,model-1")
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        result = router.resolve({"model": "other-provider/other-model"})
        assert result.provider_name == "other-provider"
        assert result.model == "other-model"

    def test_resolve_falls_back_to_default(self):
        config = _make_config(default="test-provider,model-1")
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        result = router.resolve({"model": "unknown-model"})
        assert result.provider_name == "test-provider"
        assert result.model == "model-1"

    def test_resolve_raises_without_default(self):
        config = _make_config()  # no default
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        with pytest.raises(ValueError, match="Cannot resolve model"):
            router.resolve({"model": "unknown-model"})

    def test_parse_route(self):
        provider, model = RouterEngine._parse_route("my-provider,my-model")
        assert provider == "my-provider"
        assert model == "my-model"

    def test_parse_route_invalid(self):
        with pytest.raises(ValueError, match="Invalid route format"):
            RouterEngine._parse_route("no-comma-here")
