"""FastAPI application for the LCCG gateway server."""

from __future__ import annotations

import importlib.metadata
import os
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from lccg.config.schema import GatewayConfig
from lccg.middleware.stats import StatsCollector
from lccg.provider.health import ProviderHealth
from lccg.provider.registry import ProviderRegistry
from lccg.router.engine import RouterEngine, RouteResult
from lccg.transformer.base import BaseTransformer

logger = structlog.get_logger()


def _mask_body(body: dict[str, Any], model: str = "") -> dict[str, Any]:
    """Return a minimal summary of the request body for logging."""
    messages = body.get("messages", [])
    msg_count = len(messages)
    roles = [m.get("role", "?") for m in messages[-3:]]  # last 3 messages

    result: dict[str, Any] = {
        "model": model or body.get("model", ""),
        "stream": body.get("stream", False),
        "msg_count": msg_count,
        "last_roles": roles,
    }

    # Token estimate if present
    if body.get("max_tokens"):
        result["max_tokens"] = body["max_tokens"]
    if body.get("temperature"):
        result["temperature"] = body["temperature"]

    # Tools info - full list for debugging subagent requests
    tools = body.get("tools", [])
    if tools:
        tool_names = [t.get("name", "?") for t in tools]
        result["tools"] = tool_names[:10]  # First 10 tools
        if len(tools) > 10:
            result["tools"].append(f"...+{len(tools) - 10}")
        # NOTE: Agent tool presence means the *main session* is making the request
        # (it has all tools including Agent to delegate to subagents).
        # A subagent's own request does NOT have the Agent tool.
        # So has_agent_tool=true actually means "NOT a subagent (is main session)".
        # We leave is_subagent detection to future improvement.
        result["has_agent_tool"] = "Agent" in tool_names
    else:
        result["has_agent_tool"] = False

    # Thinking info
    thinking = body.get("thinking")
    if thinking:
        result["thinking"] = thinking.get("type", "enabled")

    # Subagent detection: has_agent_tool = "Agent" in tool_names
    # - Main session: has Agent tool (can delegate to subagents) -> has_agent_tool=True
    # - Subagent: does NOT have Agent tool (is a leaf agent) -> has_agent_tool=False
    result["is_subagent"] = not result["has_agent_tool"]

    # Check for system prompt indicators
    system_prompt = ""
    for msg in messages:
        if msg.get("role") == "system":
            system_prompt = msg.get("content", "")[:200]
            break
    if system_prompt:
        result["system_prompt_preview"] = system_prompt[:100]

    return result


def _client_ip(request: Request) -> str:
    """Extract client IP, preferring forwarded headers."""
    return request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.headers.get("x-real-ip") or request.client.host if request.client else "unknown"
    )


def create_app(
    config: GatewayConfig,
    registry: ProviderRegistry,
    router: RouterEngine,
    config_path: str | None = None,
    log_queue: Any = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    health_tracker = ProviderHealth()
    stats = StatsCollector()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await app.state.registry.close_all()

    app = FastAPI(title="LCCG", version=importlib.metadata.version("lccg"), lifespan=lifespan)

    # Store shared state
    app.state.config = config
    app.state.registry = registry
    app.state.router = router
    app.state.health = health_tracker
    app.state.stats = stats
    app.state.config_path = config_path
    app.state.log_queue = log_queue

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/stats")
    async def get_stats() -> JSONResponse:
        """Get request statistics."""
        return JSONResponse(content={
            "summary": stats.get_summary(),
            "providers": stats.get_per_provider(),
            "recent": stats.get_recent(10),
        })

    @app.post("/v1/messages", response_model=None)
    async def messages(request: Request) -> JSONResponse | StreamingResponse:
        """Handle Anthropic Messages API requests."""
        request_id = uuid.uuid4().hex[:12]
        client_ip = _client_ip(request)

        # Auth check (if proxy api_key is configured)
        if config.server.api_key:
            api_key = request.headers.get("x-api-key", "")
            if api_key != config.server.api_key:
                return JSONResponse(
                    status_code=401,
                    content={"error": {"type": "authentication_error", "message": "Invalid API key"}},
                )

        # Parse request body
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": {"type": "invalid_request_error", "message": "Invalid JSON body"}},
            )

        # Full request body for debugging subagent detection
        try:
            body_str = json.dumps(body, ensure_ascii=False, indent=2)
        except Exception:
            body_str = "<serialization failed>"
        logger.info("gateway.full_request_body", request_id=request_id, body=body_str)

        # Extract all headers for subagent debugging
        headers_dict = dict(request.headers)
        # Mask sensitive headers
        headers_to_log = {k: (v[:20] + "..." if len(v) > 20 else v) for k, v in headers_dict.items()}
        # Look for agent-related headers
        agent_headers = {k: v for k, v in headers_dict.items() if "agent" in k.lower() or "subagent" in k.lower() or "x-claude" in k.lower()}

        # Log incoming request
        model = body.get("model", "")
        is_stream = body.get("stream", False)
        masked_body = _mask_body(body, model)

        # Additional debug logging for subagent detection
        has_agent = masked_body.get("has_agent_tool", False)
        is_subagent = masked_body.get("is_subagent", False)

        logger.info(
            "gateway.request",
            request_id=request_id,
            client_ip=client_ip,
            path="/v1/messages",
            method="POST",
            model=model,
            stream=is_stream,
            summary=masked_body,
            has_agent_tool=has_agent,
            is_subagent_request=is_subagent,
            agent_headers=agent_headers or None,
            all_headers=headers_to_log,
        )

        # Resolve route
        try:
            route = router.resolve(body)
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content={"error": {"type": "invalid_request_error", "message": str(e)}},
            )

        # [临时] subagent + claude-opus-4-6 硬路由到 mimo-v2-pro
        if is_subagent and model == "claude-opus-4-6":
            route = RouteResult(provider_name="xiaomi", model="mimo-v2-pro", scenario=None)
            logger.info(
                "gateway.subagent_hard_override",
                request_id=request_id,
                original_model=model,
                override_model="mimo-v2-pro",
                provider="xiaomi",
            )

        # Log route resolution for subagent debugging
        logger.info(
            "gateway.route_resolved",
            request_id=request_id,
            original_model_in_body=model,
            resolved_provider=route.provider_name,
            resolved_model=route.model,
            scenario=route.scenario,
            is_subagent=is_subagent,
        )

        # Override model with ANTHROPIC_MODEL from claude-env.json if set
        from lccg.server.api.claude_env import _load as load_claude_env
        claude_env = load_claude_env()
        env_model = claude_env.get("model", "").strip()
        stats_model = route.model
        if env_model:
            if env_model != route.model:
                logger.info(
                    "gateway.model_override",
                    request_id=request_id,
                    original_model=route.model,
                    override_model=env_model,
                    is_subagent=is_subagent,
                )
            route = RouteResult(
                provider_name=route.provider_name,
                model=env_model,
                scenario=route.scenario,
            )

        # Check provider health, try fallback if unhealthy
        if not health_tracker.is_healthy(route.provider_name) and config.router.fallback:
            fb_provider, fb_model = RouterEngine._parse_route(config.router.fallback)
            if fb_provider != route.provider_name:
                logger.warning(
                    "gateway.health_fallback",
                    request_id=request_id,
                    original=route.provider_name,
                    fallback=fb_provider,
                )
                route = RouteResult(provider_name=fb_provider, model=fb_model, scenario=route.scenario)

        # Get provider
        try:
            provider = registry.get_provider(route.provider_name)
        except KeyError:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "type": "invalid_request_error",
                        "message": f"Provider not found: {route.provider_name}",
                    }
                },
            )

        # Override model in request with the resolved model name
        body["model"] = route.model

        # Select transformer based on provider type
        transformer = registry.get_transformer_for_provider(route.provider_name)
        payload = transformer.transform_request(body)

        if is_stream:
            return await _handle_streaming(
                request, provider, payload, transformer,
                health_tracker, route.provider_name, stats, stats_model, route.scenario,
                request_id=request_id, client_ip=client_ip,
            )
        else:
            return await _handle_non_streaming(
                provider, payload, transformer, health_tracker, route.provider_name,
                router, registry, body, config, stats, stats_model, route.scenario,
                request_id=request_id, client_ip=client_ip,
            )

    # Mount UI API routers
    from lccg.server.api.config import router as config_router
    from lccg.server.api.providers import router as providers_router
    from lccg.server.api.stats import router as stats_router
    from lccg.server.api.logs import router as logs_router
    from lccg.server.api.claude_env import router as claude_env_router

    app.include_router(config_router)
    app.include_router(providers_router)
    app.include_router(stats_router)
    app.include_router(logs_router)
    app.include_router(claude_env_router)

    # Mount UI static files (must be last so API routes take precedence)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and any(static_dir.iterdir()):
        app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")

    return app


async def _handle_non_streaming(
    provider: Any,
    payload: dict[str, Any],
    transformer: BaseTransformer,
    health_tracker: ProviderHealth,
    provider_name: str,
    router: RouterEngine | None = None,
    registry: ProviderRegistry | None = None,
    body: dict[str, Any] | None = None,
    config: GatewayConfig | None = None,
    stats: StatsCollector | None = None,
    model: str = "",
    scenario: str | None = None,
    request_id: str = "",
    client_ip: str = "",
) -> JSONResponse:
    """Handle non-streaming request with fallback support."""
    timer = stats.start_timer() if stats else None
    try:
        response = await provider.send_request(payload, stream=False)
        response.raise_for_status()
        data = response.json()
        result = transformer.transform_response(data)
        health_tracker.record_success(provider_name)

        # Extract usage from response
        usage = result.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        latency = round(timer.elapsed_ms, 1) if timer else 0

        if timer:
            timer.finish(
                provider=provider_name, model=model, status="success",
                input_tokens=input_tokens, output_tokens=output_tokens, scenario=scenario,
            )

        logger.info(
            "gateway.response",
            request_id=request_id,
            client_ip=client_ip,
            provider=provider_name,
            model=model,
            scenario=scenario or None,
            status=response.status_code,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency,
        )

        return JSONResponse(content=result, status_code=response.status_code)
    except Exception as e:
        health_tracker.record_failure(provider_name)
        latency = round(timer.elapsed_ms, 1) if timer else 0
        # Try to extract provider error detail from the exception
        error_detail = str(e)
        try:
            if hasattr(e, "response") and e.response is not None:
                resp = e.response
                status = resp.status_code
                try:
                    body = resp.json()
                    error_detail = f"status={status} body={json.dumps(body, ensure_ascii=False)[:300]}"
                except Exception:
                    try:
                        body_text = resp.text
                        error_detail = f"status={status} body={body_text[:200]}"
                    except Exception:
                        error_detail = f"status={status} body=(unread)"
            elif hasattr(e, "request") and hasattr(e, "message"):
                error_detail = e.message[:200]
        except Exception:
            pass
        logger.error(
            "gateway.error",
            request_id=request_id,
            client_ip=client_ip,
            provider=provider_name,
            model=model,
            error=error_detail,
            latency_ms=latency,
        )

        if timer:
            timer.finish(provider=provider_name, model=model, status="error", error=str(e), scenario=scenario)

        # Try fallback on any error (but skip if fallback routes to the same provider)
        if (
            config and router and registry and body
            and config.router.fallback
        ):
            fb_provider_name, fb_model = RouterEngine._parse_route(config.router.fallback)
            if fb_provider_name == provider_name:
                return JSONResponse(
                    status_code=502,
                    content={
                        "error": {
                            "type": "api_error",
                            "message": f"Provider error: {e}",
                        }
                    },
                )
            logger.warning(
                "gateway.fallback",
                request_id=request_id,
                from_provider=provider_name,
                to_provider=fb_provider_name,
                error=str(e),
            )
            try:
                fb_provider = registry.get_provider(fb_provider_name)
                fb_transformer = registry.get_transformer_for_provider(fb_provider_name)
                fb_body = {**body, "model": fb_model}
                fb_payload = fb_transformer.transform_request(fb_body)
                fb_timer = stats.start_timer() if stats else None
                response = await fb_provider.send_request(fb_payload, stream=False)
                response.raise_for_status()
                data = response.json()
                result = fb_transformer.transform_response(data)
                health_tracker.record_success(fb_provider_name)

                usage = result.get("usage", {})
                fb_latency = round(fb_timer.elapsed_ms, 1) if fb_timer else 0
                if fb_timer:
                    fb_timer.finish(
                        provider=fb_provider_name, model=fb_model, status="success",
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        scenario=scenario,
                    )

                logger.info(
                    "gateway.response",
                    request_id=request_id,
                    client_ip=client_ip,
                    provider=fb_provider_name,
                    model=fb_model,
                    scenario=scenario or None,
                    status=response.status_code,
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    latency_ms=fb_latency,
                    via_fallback=True,
                )
                return JSONResponse(content=result, status_code=response.status_code)
            except Exception as fb_error:
                health_tracker.record_failure(fb_provider_name)
                fb_latency = round(fb_timer.elapsed_ms, 1) if fb_timer else 0
                fb_error_detail = str(fb_error)
                if hasattr(fb_error, "response") and fb_error.response is not None:
                    try:
                        detail = fb_error.response.json()
                        fb_error_detail = f"status={fb_error.response.status_code} body={json.dumps(detail, ensure_ascii=False)[:300]}"
                    except Exception:
                        fb_error_detail = f"status={fb_error.response.status_code} body={fb_error.response.text[:200]}"
                logger.error(
                    "gateway.error",
                    request_id=request_id,
                    client_ip=client_ip,
                    provider=fb_provider_name,
                    model=fb_model,
                    error=fb_error_detail,
                    latency_ms=fb_latency,
                    fallback_failed=True,
                )

        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "type": "api_error",
                    "message": f"Provider error: {e}",
                }
            },
        )


async def _handle_streaming(
    request: Request,
    provider: Any,
    payload: dict[str, Any],
    transformer: BaseTransformer,
    health_tracker: ProviderHealth,
    provider_name: str,
    stats: StatsCollector | None = None,
    model: str = "",
    scenario: str | None = None,
    request_id: str = "",
    client_ip: str = "",
) -> StreamingResponse:
    """Handle streaming request - proxy SSE events from provider to client."""
    timer = stats.start_timer() if stats else None
    usage_info = {"input_tokens": 0, "output_tokens": 0}
    disconnected = False
    finish_reason = "unknown"

    async def event_generator():
        nonlocal disconnected, finish_reason
        try:
            raw_stream = provider.stream_response(payload)
            async for chunk in transformer.transform_stream(raw_stream):
                if await request.is_disconnected():
                    if not disconnected:
                        disconnected = True
                        logger.info(
                            "gateway.stream_disconnected",
                            request_id=request_id,
                            client_ip=client_ip,
                            provider=provider_name,
                            model=model,
                        )
                    break
                # Extract usage from SSE events
                reason = _extract_streaming_usage(chunk, usage_info)
                if reason:
                    finish_reason = reason
                yield chunk
            if not disconnected:
                health_tracker.record_success(provider_name)
                latency = round(timer.elapsed_ms, 1) if timer else 0
                if timer:
                    timer.finish(
                        provider=provider_name, model=model, status="success",
                        input_tokens=usage_info["input_tokens"],
                        output_tokens=usage_info["output_tokens"],
                        scenario=scenario,
                    )
                logger.info(
                    "gateway.stream_done",
                    request_id=request_id,
                    client_ip=client_ip,
                    provider=provider_name,
                    model=model,
                    scenario=scenario or None,
                    finish_reason=finish_reason,
                    input_tokens=usage_info["input_tokens"],
                    output_tokens=usage_info["output_tokens"],
                    latency_ms=latency,
                )
        except Exception as e:
            health_tracker.record_failure(provider_name)
            latency = round(timer.elapsed_ms, 1) if timer else 0
            logger.error(
                "gateway.stream_error",
                request_id=request_id,
                client_ip=client_ip,
                provider=provider_name,
                model=model,
                error=str(e),
                latency_ms=latency,
            )
            if timer:
                timer.finish(provider=provider_name, model=model, status="error", error=str(e), scenario=scenario)
            error_event = {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": f"Provider error: {e}",
                },
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _extract_streaming_usage(chunk: bytes, usage_info: dict[str, int]) -> str | None:
    """Extract usage and stop reason from SSE chunk bytes.

    Returns the stop/reason string if found, otherwise None.
    """
    text = chunk.decode("utf-8", errors="replace")
    current_event = ""
    reason = None

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                continue
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            # Anthropic format: message_delta has usage and stop_reason
            if current_event == "message_delta" and "usage" in data:
                u = data["usage"]
                usage_info["input_tokens"] = u.get("input_tokens", 0)
                usage_info["output_tokens"] = u.get("output_tokens", 0)
                if "delta" in data and data["delta"].get("stop_reason"):
                    reason = data["delta"]["stop_reason"]

            # Anthropic format: message_start has message.usage
            elif current_event == "message_start" and "message" in data:
                u = data["message"].get("usage", {})
                if u.get("input_tokens"):
                    usage_info["input_tokens"] = u["input_tokens"]

            # OpenAI format: final chunk has usage
            elif "usage" in data and current_event == "":
                u = data["usage"]
                usage_info["input_tokens"] = u.get("prompt_tokens", u.get("input_tokens", 0))
                usage_info["output_tokens"] = u.get("completion_tokens", u.get("output_tokens", 0))
                if "choices" in data:
                    cr = data["choices"][0].get("finish_reason")
                    if cr:
                        reason = cr

    return reason
