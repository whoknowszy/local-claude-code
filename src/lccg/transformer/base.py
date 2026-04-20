"""Base transformer abstraction for request/response format conversion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class BaseTransformer(ABC):
    """Abstract base class for transformers that convert between API formats."""

    @abstractmethod
    def transform_request(self, anthropic_request: dict[str, Any]) -> dict[str, Any]:
        """Convert an Anthropic-format request to the provider's format.

        Args:
            anthropic_request: The original request in Anthropic Messages API format.

        Returns:
            The request payload in the provider's expected format.
        """

    @abstractmethod
    def transform_response(self, provider_response: dict[str, Any]) -> dict[str, Any]:
        """Convert a provider's response to Anthropic format.

        Args:
            provider_response: The response from the provider.

        Returns:
            The response in Anthropic Messages API format.
        """

    async def transform_stream(self, stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        """Convert streaming response chunks.

        Default: pass-through. Override for format conversion (e.g. OpenAI→Anthropic SSE).
        """
        async for chunk in stream:
            yield chunk
