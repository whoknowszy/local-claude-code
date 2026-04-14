"""Base provider abstraction for LLM API communication."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx

from lccg.config.schema import ProviderConfig


class ProviderHTTPError(Exception):
    """Raised when upstream provider returns an HTTP error."""

    def __init__(self, status_code: int, body: str, headers: dict | None = None):
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}
        super().__init__(f"Provider returned HTTP {status_code}: {body[:200]}")


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.name = config.name
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            headers.update(self.config.headers)

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                headers=headers,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @abstractmethod
    async def send_request(
        self,
        payload: dict[str, Any],
        stream: bool = False,
    ) -> httpx.Response:
        """Send a request to the provider API.

        Args:
            payload: The request payload (already transformed to provider format).
            stream: Whether to request streaming response.

        Returns:
            httpx.Response object.
        """

    @abstractmethod
    async def stream_response(
        self,
        payload: dict[str, Any],
    ) -> AsyncIterator[bytes]:
        """Stream response chunks from the provider.

        Args:
            payload: The request payload (already transformed to provider format).

        Yields:
            Raw bytes from the streaming response.
        """
