"""Provider registry for managing provider instances."""

from __future__ import annotations

from lccg.config.schema import GatewayConfig, ProviderConfig, ProviderType
from lccg.provider.anthropic_provider import AnthropicProvider
from lccg.provider.base import BaseProvider
from lccg.provider.openai_provider import OpenAIProvider
from lccg.transformer.anthropic_passthru import AnthropicPassthruTransformer
from lccg.transformer.base import BaseTransformer
from lccg.transformer.openai_convert import OpenAIConvertTransformer


_PROVIDER_MAP: dict[ProviderType, type[BaseProvider]] = {
    ProviderType.ANTHROPIC: AnthropicProvider,
    ProviderType.OPENAI: OpenAIProvider,
}

_TRANSFORMER_MAP: dict[ProviderType, type[BaseTransformer]] = {
    ProviderType.ANTHROPIC: AnthropicPassthruTransformer,
    ProviderType.OPENAI: OpenAIConvertTransformer,
}


class ProviderRegistry:
    """Registry that manages provider instances based on configuration."""

    def __init__(self, config: GatewayConfig) -> None:
        self._providers: dict[str, BaseProvider] = {}
        self._model_to_provider: dict[str, str] = {}
        self._provider_types: dict[str, ProviderType] = {}

        for provider_config in config.providers:
            provider = self._create_provider(provider_config)
            self._providers[provider_config.name] = provider
            self._provider_types[provider_config.name] = provider_config.type
            for model in provider_config.models:
                self._model_to_provider[model] = provider_config.name

    def _create_provider(self, config: ProviderConfig) -> BaseProvider:
        provider_cls = _PROVIDER_MAP.get(config.type)
        if provider_cls is None:
            raise ValueError(f"Unknown provider type: {config.type}")
        return provider_cls(config)

    def get_provider(self, name: str) -> BaseProvider:
        if name not in self._providers:
            raise KeyError(f"Provider not found: {name}")
        return self._providers[name]

    def get_provider_for_model(self, model: str) -> BaseProvider:
        """Find the provider that serves a given model."""
        if model in self._model_to_provider:
            return self._providers[self._model_to_provider[model]]

        # Try partial match (e.g. "minimax/MiniMax-M2.1" -> provider "minimax", model "MiniMax-M2.1")
        if "/" in model:
            provider_name, model_name = model.split("/", 1)
            if provider_name in self._providers:
                return self._providers[provider_name]

        raise KeyError(f"No provider found for model: {model}")

    def get_provider_name_for_model(self, model: str) -> str:
        if model in self._model_to_provider:
            return self._model_to_provider[model]
        if "/" in model:
            provider_name = model.split("/", 1)[0]
            if provider_name in self._providers:
                return provider_name
        raise KeyError(f"No provider found for model: {model}")

    async def close_all(self) -> None:
        for provider in self._providers.values():
            await provider.close()

    @property
    def provider_names(self) -> list[str]:
        return list(self._providers.keys())

    def get_transformer_for_provider(self, provider_name: str) -> BaseTransformer:
        """Get the appropriate transformer for a provider based on its type."""
        provider_type = self._provider_types.get(provider_name)
        if provider_type is None:
            raise KeyError(f"Provider not found: {provider_name}")
        transformer_cls = _TRANSFORMER_MAP.get(provider_type)
        if transformer_cls is None:
            raise ValueError(f"No transformer for provider type: {provider_type}")
        return transformer_cls()
