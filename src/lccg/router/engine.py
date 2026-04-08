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

    def resolve(self, request: dict[str, Any], request_id: str = "") -> RouteResult:
        """Resolve the target provider and model for a request.

        Priority:
        1. Explicit provider/model prefix (e.g. "minimax/MiniMax-M2.7")
        2. Scenario-based routing (long_context, background, web_search, think)
        3. Model name lookup in registry
        4. Default fallback
        """
        model = request.get("model", "")
        extras = {"request_id": request_id} if request_id else {}

        # 1. If the model specifies a provider prefix, use it directly
        if "/" in model:
            provider_name = model.split("/", 1)[0]
            actual_model = model.split("/", 1)[1]
            logger.info(
                "router.decision",
                **extras,
                model=model,
                route_reason="explicit prefix 'provider/model'",
                final_provider=provider_name,
                final_model=actual_model,
            )
            return RouteResult(provider_name=provider_name, model=actual_model)

        # Build scenario analysis for comprehensive logging
        scenario_decision = self._analyze_scenarios(request)
        chosen_scenario = scenario_decision.get("triggered")

        # 2. Scenario-based routing
        if chosen_scenario:
            route_str = getattr(self._router, chosen_scenario, None)
            if route_str:
                try:
                    provider_name, model_name = self._parse_route(route_str)
                    logger.info(
                        "router.decision",
                        **extras,
                        model=model,
                        route_reason=f"scenario: {chosen_scenario}",
                        scenario_detail=scenario_decision.get("detail", ""),
                        final_provider=provider_name,
                        final_model=model_name,
                        scenario_chain=scenario_decision.get("chain", []),
                    )
                    return RouteResult(provider_name=provider_name, model=model_name, scenario=chosen_scenario)
                except ValueError:
                    pass

        # 3. Try to find a provider that serves this model
        try:
            provider = self._registry.get_provider_for_model(model)
            logger.info(
                "router.decision",
                **extras,
                model=model,
                route_reason="registry lookup (no scenario matched)",
                scenario_chain=scenario_decision.get("chain", []),
                final_provider=provider.name,
                final_model=model,
            )
            return RouteResult(provider_name=provider.name, model=model)
        except KeyError:
            pass

        # 4. Fall back to router default
        if self._router.default:
            provider_name, model_name = self._parse_route(self._router.default)
            logger.info(
                "router.decision",
                **extras,
                model=model,
                route_reason=f"default fallback (model '{model}' not found in any provider)",
                scenario_chain=scenario_decision.get("chain", []),
                final_provider=provider_name,
                final_model=model_name,
            )
            return RouteResult(provider_name=provider_name, model=model_name)

        raise ValueError(
            f"Cannot resolve model '{model}': no provider found and no default route configured"
        )

    def _analyze_scenarios(self, request: dict[str, Any]) -> dict[str, Any]:
        """Analyze all scenarios and return the triggered one plus full decision chain."""
        chain: list[dict[str, Any]] = []
        triggered: str | None = None
        detail = ""

        model = request.get("model", "")

        # long_context
        if self._router.long_context:
            token_count = count_tokens(request)
            threshold = self._router.long_context_threshold
            hit = token_count > threshold
            route = self._router.long_context
            chain.append({
                "scenario": "long_context",
                "enabled": True,
                "tokens": token_count,
                "threshold": threshold,
                "hit": hit,
                "route": route,
            })
            if hit and not triggered:
                triggered = "long_context"
                detail = f"tokens {token_count} > threshold {threshold}"
        else:
            chain.append({"scenario": "long_context", "enabled": False})

        # background: haiku model
        bg_hit = bool(model and "haiku" in model.lower() and self._router.background)
        if self._router.background:
            chain.append({
                "scenario": "background",
                "enabled": True,
                "model": model,
                "hint": "model contains 'haiku'",
                "hit": bg_hit,
                "route": self._router.background,
            })
            if bg_hit and not triggered:
                triggered = "background"
                detail = f"model '{model}' matches 'haiku' pattern"
        else:
            chain.append({"scenario": "background", "enabled": False})

        # web_search: tools
        ws_hit = False
        if self._router.web_search:
            tools = request.get("tools", [])
            tool_names = [t.get("name", "") for t in tools if isinstance(t, dict)]
            ws_hit = any(t.startswith("web_search") for t in tool_names)
            chain.append({
                "scenario": "web_search",
                "enabled": True,
                "tools": tool_names[:5],
                "hit": ws_hit,
                "route": self._router.web_search,
            })
            if ws_hit and not triggered:
                triggered = "web_search"
                detail = f"tool '{next(t for t in tool_names if t.startswith('web_search'))}' found"
        else:
            chain.append({"scenario": "web_search", "enabled": False})

        # think: thinking.enabled
        th_hit = False
        thinking = request.get("thinking")
        if thinking and isinstance(thinking, dict) and thinking.get("type") == "enabled" and self._router.think:
            th_hit = True
            chain.append({
                "scenario": "think",
                "enabled": True,
                "hit": th_hit,
                "route": self._router.think,
            })
            if th_hit and not triggered:
                triggered = "think"
                detail = "thinking.type='enabled'"
        else:
            reason = "not enabled" if not self._router.think else "thinking not requested"
            chain.append({"scenario": "think", "enabled": bool(self._router.think), "hit": False, "reason": reason})

        return {"triggered": triggered, "detail": detail, "chain": chain}

    @staticmethod
    def _parse_route(route: str) -> tuple[str, str]:
        """Parse a route string like 'provider,model' into components."""
        parts = route.split(",", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid route format: {route!r}. Expected 'provider,model'")
        return parts[0].strip(), parts[1].strip()
