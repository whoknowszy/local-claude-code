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
        payload = {**payload, "stream": True}

        logger.debug(
            "openai_provider.stream_start",
            provider=self.name,
            url=self._base_url,
        )

        try:
            async with self.client.stream(
                "POST",
                self._base_url,
                json=payload,
            ) as response:
                # Check for HTTP errors before starting to iterate
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
