"""Provider implementation for OpenAI-compatible APIs."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
import structlog

from lccg.config.schema import ProviderConfig
from lccg.provider.base import BaseProvider

logger = structlog.get_logger()


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
        """Send request to OpenAI-compatible API."""
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

        response = await self.client.post(
            self._base_url,
            json=payload,
        )

        resp_text = await response.aread()
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
        payload = {**payload, "stream": True}

        logger.debug(
            "openai_provider.stream_start",
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
