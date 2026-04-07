"""Router engine for selecting provider and model based on request context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from lccg.config.schema import GatewayConfig
from lccg.provider.registry import ProviderRegistry
from lccg.router.token_counter import count_tokens

logger = structlog.get_logger()


@dataclass
class RouteResult:
    provider_name: str
    model: str
    scenario: str | None = field(default=None)


class RouterEngine:
    """Routes requests to the appropriate provider and model based on configuration."""

    def __init__(self, config: GatewayConfig, registry: ProviderRegistry) -> None:
        self._config = config
        self._registry = registry
        self._router = config.router

    def resolve(self, request: dict[str, Any]) -> RouteResult:
        """Resolve the target provider and model for a request.

        Priority:
        1. Explicit provider/model prefix (e.g. "minimax/MiniMax-M2.7")
        2. Scenario-based routing (long_context, background, web_search, think)
        3. Model name lookup in registry
        4. Default fallback
        """
        model = request.get("model", "")

        # 1. If the model specifies a provider prefix, use it directly
        if "/" in model:
            provider_name = model.split("/", 1)[0]
            actual_model = model.split("/", 1)[1]
            return RouteResult(provider_name=provider_name, model=actual_model)

        # 2. Scenario-based routing
        scenario = self._detect_scenario(request)
        if scenario:
            route_str = getattr(self._router, scenario, None) or getattr(self._router, scenario.replace("_", "_"), None)
            if route_str:
                try:
                    provider_name, model_name = self._parse_route(route_str)
                    logger.info(
                        "router.scenario_route",
                        scenario=scenario,
                        provider=provider_name,
                        model=model_name,
                    )
                    return RouteResult(provider_name=provider_name, model=model_name, scenario=scenario)
                except ValueError:
                    pass

        # 3. Try to find a provider that serves this model
        try:
            provider = self._registry.get_provider_for_model(model)
            return RouteResult(provider_name=provider.name, model=model)
        except KeyError:
            pass

        # 4. Fall back to router default
        if self._router.default:
            provider_name, model_name = self._parse_route(self._router.default)
            logger.info(
                "router.fallback_to_default",
                original_model=model,
                fallback=f"{provider_name},{model_name}",
            )
            return RouteResult(provider_name=provider_name, model=model_name)

        raise ValueError(
            f"Cannot resolve model '{model}': no provider found and no default route configured"
        )

    def _detect_scenario(self, request: dict[str, Any]) -> str | None:
        """Detect routing scenario based on request characteristics.

        Returns the scenario name (matching RouterConfig field names) or None.
        """
        # a. Long context: token count exceeds threshold
        if self._router.long_context:
            token_count = count_tokens(request)
            if token_count > self._router.long_context_threshold:
                logger.info(
                    "router.long_context_detected",
                    tokens=token_count,
                    threshold=self._router.long_context_threshold,
                )
                return "long_context"

        # b. Background: haiku model variants
        model = request.get("model", "")
        if model and "haiku" in model.lower() and self._router.background:
            return "background"

        # c. Web search: tools contain web_search
        tools = request.get("tools", [])
        if tools and any(t.get("name", "").startswith("web_search") for t in tools if isinstance(t, dict)):
            if self._router.web_search:
                return "web_search"

        # d. Thinking enabled
        thinking = request.get("thinking")
        if thinking and isinstance(thinking, dict) and thinking.get("type") == "enabled":
            if self._router.think:
                return "think"

        return None

    @staticmethod
    def _parse_route(route: str) -> tuple[str, str]:
        """Parse a route string like 'provider,model' into components."""
        parts = route.split(",", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid route format: {route!r}. Expected 'provider,model'")
        return parts[0].strip(), parts[1].strip()
