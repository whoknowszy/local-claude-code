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

    # --- model_map tests ---

    def test_resolve_model_map_string(self):
        """model_map with a single string route resolves correctly."""
        config = _make_config(
            default="test-provider,default-model",
            model_map={"claude-sonnet-4-6": "other-provider,their-model"},
        )
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        result = router.resolve({"model": "claude-sonnet-4-6"})
        assert result.provider_name == "other-provider"
        assert result.model == "their-model"
        assert result.scenario == "model_map"

    def test_resolve_model_map_list(self):
        """model_map with a list takes the first item as primary route."""
        config = _make_config(
            default="test-provider,default-model",
            model_map={
                "claude-opus-4-6": [
                    "other-provider,primary-model",
                    "test-provider,fallback-model",
                ],
            },
        )
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        result = router.resolve({"model": "claude-opus-4-6"})
        assert result.provider_name == "other-provider"
        assert result.model == "primary-model"
        assert result.scenario == "model_map"

    def test_resolve_model_map_priority_over_registry(self):
        """model_map takes priority over registry lookup."""
        config = _make_config(
            default="test-provider,default-model",
            model_map={"model-1": "other-provider,override-model"},
        )
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        # model-1 is registered to test-provider, but model_map overrides it
        result = router.resolve({"model": "model-1"})
        assert result.provider_name == "other-provider"
        assert result.model == "override-model"
        assert result.scenario == "model_map"

    def test_resolve_explicit_prefix_priority_over_model_map(self):
        """Explicit 'provider/model' prefix takes priority over model_map."""
        config = _make_config(
            default="test-provider,default-model",
            model_map={"claude-sonnet-4-6": "other-provider,their-model"},
        )
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        result = router.resolve({"model": "test-provider/model-1"})
        assert result.provider_name == "test-provider"
        assert result.model == "model-1"
        # Priority 1 (explicit prefix), not model_map

    # --- fallback chain tests ---

    def test_fallback_chain_from_model_map_list(self):
        """resolve_fallback_chain includes model_map list items after the first."""
        config = _make_config(
            model_map={
                "claude-opus-4-6": [
                    "test-provider,primary",
                    "other-provider,secondary",
                ],
            },
        )
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        chain = router.resolve_fallback_chain(model="claude-opus-4-6", failed_provider="test-provider")
        provider_names = [r.provider_name for r in chain]
        assert "other-provider" in provider_names  # from model_map list
        assert "test-provider" not in provider_names  # already failed

    def test_fallback_chain_by_provider_priority(self):
        """resolve_fallback_chain sorts by provider priority (lower number first)."""
        providers = [
            ProviderConfig(
                name="low-priority",
                type=ProviderType.ANTHROPIC,
                priority=100,
                base_url="https://api.low.com/v1/messages",
                api_key="sk-low",
                models=["model-x"],
            ),
            ProviderConfig(
                name="high-priority",
                type=ProviderType.ANTHROPIC,
                priority=1,
                base_url="https://api.high.com/v1/messages",
                api_key="sk-high",
                models=["model-y"],
            ),
            ProviderConfig(
                name="mid-priority",
                type=ProviderType.ANTHROPIC,
                priority=50,
                base_url="https://api.mid.com/v1/messages",
                api_key="sk-mid",
                models=["model-z"],
            ),
        ]
        from lccg.config.schema import GatewayConfig, RouterConfig

        config = GatewayConfig(providers=providers, router=RouterConfig())
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        chain = router.resolve_fallback_chain(model="some-model", failed_provider="low-priority")
        provider_names = [r.provider_name for r in chain]
        assert provider_names[0] == "high-priority"  # priority 1
        assert provider_names[1] == "mid-priority"    # priority 50
        # Each fallback provider uses its own registered model, not the original model
        assert chain[0].model == "model-y"
        assert chain[1].model == "model-z"

    def test_fallback_chain_uses_provider_model_not_original(self):
        """Fallback to a provider should use that provider's registered model, not the original model."""
        config = _make_config(default="test-provider,model-1")
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        # Request for "model-1" on test-provider fails; fallback to other-provider
        # other-provider only has "other-model", so it should use that, not "model-1"
        chain = router.resolve_fallback_chain(model="model-1", failed_provider="test-provider")
        assert len(chain) >= 1
        fb = chain[0]
        assert fb.provider_name == "other-provider"
        assert fb.model == "other-model"  # NOT "model-1"

    def test_fallback_chain_skips_failed_provider(self):
        """resolve_fallback_chain skips the already-failed provider."""
        config = _make_config(default="test-provider,default-model")
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        chain = router.resolve_fallback_chain(model="model-1", failed_provider="test-provider")
        provider_names = [r.provider_name for r in chain]
        assert "test-provider" not in provider_names
        assert "other-provider" in provider_names  # second provider is included

    def test_fallback_chain_backward_compat(self):
        """resolve_fallback_chain appends router.fallback at the end if not already covered."""
        # router.fallback can point to a provider not in priority list
        # So extra-provider only appears in fallback (not in providers config)
        providers = [
            ProviderConfig(
                name="test-provider",
                type=ProviderType.ANTHROPIC,
                priority=10,
                base_url="https://api.test.com/v1/messages",
                api_key="sk-test",
                models=["model-1"],
            ),
        ]
        from lccg.config.schema import GatewayConfig, RouterConfig

        config = GatewayConfig(
            providers=providers,
            router=RouterConfig(fallback="extra-provider,fallback-model"),
        )
        registry = ProviderRegistry(config)
        router = RouterEngine(config, registry)

        chain = router.resolve_fallback_chain(model="model-1", failed_provider="test-provider")
        # fallback_compat should be last
        assert chain[-1].scenario == "fallback_compat"
        assert chain[-1].provider_name == "extra-provider"
