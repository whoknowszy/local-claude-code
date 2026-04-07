"""Provider implementation for Anthropic-compatible APIs."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
import structlog

from lccg.config.schema import ProviderConfig
from lccg.provider.base import BaseProvider

logger = structlog.get_logger()


class AnthropicProvider(BaseProvider):
    """Provider for APIs that natively support the Anthropic Messages API format.

    The request payload is sent as-is to the provider's base_url.
    """

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._base_url = config.base_url.rstrip("/")

    def _build_headers(self) -> dict[str, str]:
        """Build request headers for Anthropic-compatible APIs."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.config.api_key:
            if self.config.auth_scheme == "bearer":
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            else:
                headers["x-api-key"] = self.config.api_key
        headers.update(self.config.headers)
        return headers

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                headers=self._build_headers(),
            )
        return self._client

    async def send_request(
        self,
        payload: dict[str, Any],
        stream: bool = False,
    ) -> httpx.Response:
        """Send request to Anthropic-compatible API."""
        if stream:
            payload = {**payload, "stream": True}

        headers = self._build_headers()
        log_headers = {k: (v[:20] + "..." if len(str(v)) > 20 else v) for k, v in headers.items()}

        logger.info(
            "anthropic_provider.request",
            provider=self.name,
            url=self._base_url,
            headers=log_headers,
            body=json.dumps(payload, ensure_ascii=False),
        )

        response = await self.client.post(
            self._base_url,
            json=payload,
        )

        resp_text = await response.aread()
        logger.info(
            "anthropic_provider.response",
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
        """Stream response from Anthropic-compatible API."""
        payload = {**payload, "stream": True}

        logger.debug(
            "anthropic_provider.stream_start",
            provider=self.name,
            url=self._base_url,
        )

        async with self.client.stream(
            "POST",
            self._base_url,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                if chunk:
                    yield chunk
