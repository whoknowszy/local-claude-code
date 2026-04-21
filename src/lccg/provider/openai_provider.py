"""Provider implementation for OpenAI-compatible APIs."""

from __future__ import annotations

import gzip
import json
import traceback
from collections.abc import AsyncIterator
from typing import Any

import httpx
import structlog

from lccg.config.schema import ProviderConfig
from lccg.provider.base import BaseProvider, ProviderHTTPError

logger = structlog.get_logger()

_MISSING_REASONING_PLACEHOLDER = (
    "Reasoning content was not available in the upstream assistant tool-call history."
)
_MISSING_REASONING_ERROR = "thinking is enabled but reasoning_content is missing"


def sanitize_reasoning_tool_call_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure thinking requests keep reasoning_content on assistant tool-call messages."""
    if not (payload.get("enable_thinking") or payload.get("reasoning_effort")):
        return payload

    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload

    sanitized_messages: list[Any] = []
    changed = False

    for msg in messages:
        if (
            isinstance(msg, dict)
            and msg.get("role") == "assistant"
            and msg.get("tool_calls")
            and not msg.get("reasoning_content")
        ):
            reordered: dict[str, Any] = {}
            for key, value in msg.items():
                if key == "tool_calls":
                    reordered["reasoning_content"] = _MISSING_REASONING_PLACEHOLDER
                if key != "reasoning_content":
                    reordered[key] = value
            if "reasoning_content" not in reordered:
                reordered["reasoning_content"] = _MISSING_REASONING_PLACEHOLDER
            sanitized_messages.append(reordered)
            changed = True
        else:
            sanitized_messages.append(msg)

    if not changed:
        return payload

    return {**payload, "messages": sanitized_messages}


def is_missing_reasoning_content_error(status_code: int, body: str) -> bool:
    """Return true for Moonshot/Kimi's thinking + tool-call history validation error."""
    return status_code == 400 and _MISSING_REASONING_ERROR in body


def disable_reasoning_for_retry(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of payload with OpenAI-compatible thinking flags removed."""
    retry_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"enable_thinking", "reasoning_effort"}
    }
    retry_payload["enable_thinking"] = False
    retry_payload["thinking"] = {"type": "disabled"}

    return collapse_tool_call_history_for_retry(retry_payload)


def collapse_tool_call_history_for_retry(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert prior tool-call history to text so thinking models avoid tool-call validation."""
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload

    collapsed_messages: list[Any] = []
    changed = False

    for msg in messages:
        if not isinstance(msg, dict):
            collapsed_messages.append(msg)
            continue

        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            parts: list[str] = []
            content = msg.get("content")
            if content:
                parts.append(str(content))
            parts.append("Tool call history:")
            for tool_call in msg.get("tool_calls", []):
                if not isinstance(tool_call, dict):
                    continue
                func = tool_call.get("function", {})
                name = func.get("name", "")
                arguments = func.get("arguments", "")
                tool_id = tool_call.get("id", "")
                parts.append(f"- {name}({arguments}) [id: {tool_id}]")

            collapsed_messages.append({"role": "assistant", "content": "\n".join(parts)})
            changed = True
            continue

        if msg.get("role") == "tool":
            tool_id = msg.get("tool_call_id", "")
            content = msg.get("content", "")
            collapsed_messages.append(
                {
                    "role": "user",
                    "content": f"Tool result for {tool_id}:\n{content}",
                }
            )
            changed = True
            continue

        if "reasoning_content" in msg:
            collapsed_messages.append(
                {
                    key: value
                    for key, value in msg.items()
                    if key != "reasoning_content"
                }
            )
            changed = True
            continue

        collapsed_messages.append(msg)

    if not changed:
        return payload

    return {**payload, "messages": collapsed_messages}


class OpenAIProvider(BaseProvider):
    """Provider for APIs that support the OpenAI Chat Completions format.

    The request payload is converted to OpenAI format by the transformer before being sent.
    """

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._base_url = config.base_url.rstrip("/")

    def _build_headers(self) -> dict[str, str]:
        """Build request headers for OpenAI-compatible APIs."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        headers.update(self.config.headers)
        return headers

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = self._build_headers()
            headers["Accept-Encoding"] = "identity"
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                headers=headers,
                follow_redirects=True,
            )
        return self._client

    async def send_request(
        self,
        payload: dict[str, Any],
        stream: bool = False,
    ) -> httpx.Response:
        """Send request to OpenAI-compatible API."""
        payload = sanitize_reasoning_tool_call_payload(payload)
        if stream:
            payload = {**payload, "stream": True}

        headers = self._build_headers()
        log_headers = {k: (v[:20] + "..." if len(str(v)) > 20 else v) for k, v in headers.items()}

        logger.info(
            "openai_provider.request",
            provider=self.name,
            url=self._base_url,
            headers=log_headers,
            body=json.dumps(payload, ensure_ascii=False),
        )

        try:
            response = await self.client.post(
                self._base_url,
                json=payload,
            )
            resp_raw = await response.aread()
            if is_missing_reasoning_content_error(
                response.status_code,
                resp_raw.decode("utf-8", errors="replace"),
            ):
                payload = disable_reasoning_for_retry(payload)
                logger.warning(
                    "openai_provider.reasoning_retry",
                    provider=self.name,
                    url=self._base_url,
                    reason="upstream rejected thinking tool-call history",
                )
                response = await self.client.post(
                    self._base_url,
                    json=payload,
                )
                resp_raw = await response.aread()
            # Check for HTTP errors and raise ProviderHTTPError for 4XX/5XX
            if response.status_code >= 400:
                raise ProviderHTTPError(
                    status_code=response.status_code,
                    body=resp_raw.decode("utf-8", errors="replace")[:500],
                    headers=dict(response.headers),
                )
        except httpx.TimeoutException as e:
            logger.error(
                "openai_provider.timeout",
                provider=self.name,
                url=self._base_url,
                error_type=type(e).__name__,
                timeout_config=self.config.timeout,
                traceback=traceback.format_exc(),
            )
            raise
        except httpx.ConnectError as e:
            logger.error(
                "openai_provider.connect_error",
                provider=self.name,
                url=self._base_url,
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
            )
            raise
        except Exception as e:
            logger.error(
                "openai_provider.request_error",
                provider=self.name,
                url=self._base_url,
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
            )
            raise
        try:
            resp_text = gzip.decompress(resp_raw)
        except Exception:
            resp_text = resp_raw
        logger.info(
            "openai_provider.response",
            provider=self.name,
            status=response.status_code,
            body=resp_text.decode("utf-8", errors="replace")[:500],
        )
        # Rebuild response since body was consumed
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=resp_text,
            request=response.request,
        )

    async def stream_response(
        self,
        payload: dict[str, Any],
    ) -> AsyncIterator[bytes]:
        """Stream response from OpenAI-compatible API."""
        payload = sanitize_reasoning_tool_call_payload(payload)
        payload = {**payload, "stream": True}

        logger.debug(
            "openai_provider.stream_start",
            provider=self.name,
            url=self._base_url,
        )

        try:
            retry_payload: dict[str, Any] | None = None

            async with self.client.stream(
                "POST",
                self._base_url,
                json=payload,
            ) as response:
                # Check for HTTP errors before starting to iterate
                if response.status_code >= 400:
                    body = await response.aread()
                    body_text = body.decode("utf-8", errors="replace")[:500]
                    if is_missing_reasoning_content_error(response.status_code, body_text):
                        retry_payload = disable_reasoning_for_retry(payload)
                        logger.warning(
                            "openai_provider.reasoning_retry",
                            provider=self.name,
                            url=self._base_url,
                            reason="upstream rejected thinking tool-call history",
                            stream=True,
                        )
                    else:
                        raise ProviderHTTPError(
                            status_code=response.status_code,
                            body=body_text,
                            headers=dict(response.headers),
                        )
                else:
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            yield chunk
                    return

            if retry_payload is not None:
                async with self.client.stream(
                    "POST",
                    self._base_url,
                    json=retry_payload,
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ProviderHTTPError(
                            status_code=response.status_code,
                            body=body.decode("utf-8", errors="replace")[:500],
                            headers=dict(response.headers),
                        )
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            yield chunk
        except httpx.TimeoutException as e:
            logger.error(
                "openai_provider.stream_timeout",
                provider=self.name,
                url=self._base_url,
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
            )
            raise
        except Exception as e:
            logger.error(
                "openai_provider.stream_error",
                provider=self.name,
                url=self._base_url,
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
            )
            raise
