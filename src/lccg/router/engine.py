"""Router engine for selecting provider and model based on request context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from lccg.config.schema import GatewayConfig, ProviderConfig
from lccg.provider.registry import ProviderRegistry

logger = structlog.get_logger()


@dataclass
class RouteResult:
    provider_name: str
    model: str
    scenario: str | None = field(default=None)


class RouterEngine:
    """Routes requests to the appropriate provider and model based on configuration."""

    def __init__(
        self,
        config: GatewayConfig,
        registry: ProviderRegistry,
        providers_config: list[ProviderConfig] | None = None,
    ) -> None:
        self._config = config
        self._registry = registry
        self._router = config.router
        self._providers_config = (
            providers_config if providers_config is not None else config.providers
        )

    def resolve(self, request: dict[str, Any], request_id: str = "") -> RouteResult:
        """Resolve the target provider and model for a request.

        Priority:
        1. Explicit provider/model prefix (e.g. "minimax/MiniMax-M2.7")
        2. model_map alias mapping (model_map config)
        3. Model name lookup in registry
        4. Default fallback
        """
        model = request.get("model", "")
        extras = {"request_id": request_id} if request_id else {}

        # 1. Explicit provider prefix
        if "/" in model:
            provider_name = model.split("/", 1)[0]
            actual_model = model.split("/", 1)[1]
            logger.info(
                "router.decision",
                **extras,
                model=model,
                route_reason="explicit prefix",
                final_provider=provider_name,
                final_model=actual_model,
            )
            return RouteResult(provider_name=provider_name, model=actual_model)

        # 2. model_map alias mapping
        model_map = self._router.model_map
        if model in model_map:
            route_value = model_map[model]
            if isinstance(route_value, list) and not route_value:
                raise ValueError(f"model_map route for {model!r} is empty")
            primary = route_value[0] if isinstance(route_value, list) else route_value
            provider_name, mapped_model = self._parse_route(primary)
            logger.info(
                "router.decision",
                **extras,
                model=model,
                route_reason="model_map alias",
                final_provider=provider_name,
                final_model=mapped_model,
            )
            return RouteResult(
                provider_name=provider_name, model=mapped_model, scenario="model_map"
            )

        # 3. Registry lookup
        try:
            provider = self._registry.get_provider_for_model(model)
            logger.info(
                "router.decision",
                **extras,
                model=model,
                route_reason="registry lookup",
                final_provider=provider.name,
                final_model=model,
            )
            return RouteResult(provider_name=provider.name, model=model)
        except KeyError:
            pass

        # 4. Default fallback
        if self._router.default:
            provider_name, model_name = self._parse_route(self._router.default)
            logger.info(
                "router.decision",
                **extras,
                model=model,
                route_reason="default fallback",
                final_provider=provider_name,
                final_model=model_name,
            )
            return RouteResult(provider_name=provider_name, model=model_name)

        # 5. Auto-select highest priority provider
        if self._providers_config:
            sorted_providers = sorted(
                self._providers_config,
                key=lambda pc: (pc.priority, pc.name),
            )
            pc = sorted_providers[0]
            auto_model = model if model in pc.models else (pc.models[0] if pc.models else model)
            logger.info(
                "router.decision",
                **extras,
                model=model,
                route_reason="auto_default",
                final_provider=pc.name,
                final_model=auto_model,
            )
            return RouteResult(provider_name=pc.name, model=auto_model)

        raise ValueError(
            f"Cannot resolve model '{model}': no provider found and no default route configured"
        )

    def resolve_fallback_chain(
        self,
        model: str,
        failed_provider: str,
    ) -> list[RouteResult]:
        """Generate ordered fallback chain excluding the failed provider.

        Build chain from:
        1. model_map list items (skip first/main route)
        2. Other providers sorted by priority (lower number = higher priority)
        3. Backward-compatible router.fallback (at end)
        """
        chain: list[RouteResult] = []
        seen: set[str] = {failed_provider}

        # 1. model_map list items after the first one
        model_map = self._router.model_map
        if model in model_map:
            route_value = model_map[model]
            if isinstance(route_value, list):
                for entry in route_value[1:]:  # skip first (already failed main route)
                    try:
                        p, m = self._parse_route(entry)
                    except ValueError:
                        continue
                    if p not in seen:
                        chain.append(
                            RouteResult(provider_name=p, model=m, scenario="model_map_fallback")
                        )
                        seen.add(p)

        # 2. Other providers sorted by priority, then provider name for stability
        sorted_providers = sorted(
            self._providers_config,
            key=lambda pc: (pc.priority, pc.name),
        )
        for pc in sorted_providers:
            if pc.name not in seen and pc.enabled:
                # Use the provider's registered model name, not the original model
                fb_model = model if model in pc.models else (pc.models[0] if pc.models else model)
                chain.append(
                    RouteResult(provider_name=pc.name, model=fb_model, scenario="priority_fallback")
                )
                seen.add(pc.name)

        # 3. Backward-compatible router.fallback (at end)
        if self._router.fallback:
            try:
                p, m = self._parse_route(self._router.fallback)
                if p not in seen:
                    chain.append(RouteResult(provider_name=p, model=m, scenario="fallback_compat"))
            except ValueError:
                pass

        return chain

    @staticmethod
    def _parse_route(route: str) -> tuple[str, str]:
        """Parse a route string like 'provider,model' into components."""
        parts = route.split(",", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid route format: {route!r}. Expected 'provider,model'")
        return parts[0].strip(), parts[1].strip()
