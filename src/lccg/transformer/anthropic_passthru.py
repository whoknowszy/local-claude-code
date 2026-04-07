"""Anthropic passthrough transformer with field cleanup for third-party providers."""

from __future__ import annotations

from typing import Any

from lccg.transformer.base import BaseTransformer


class AnthropicPassthruTransformer(BaseTransformer):
    """Pass-through transformer for providers that natively support Anthropic API format.

    Cleans up fields that third-party providers may not support:
    - system: converts array format to string
    - output_config: removed (json_schema not universally supported)
    - metadata: removed (Anthropic-specific)
    - temperature: ensures float
    """

    # Fields to remove (not supported by most third-party providers)
    _REMOVE_FIELDS = {"metadata", "output_config"}

    def transform_request(self, anthropic_request: dict[str, Any]) -> dict[str, Any]:
        """Clean up request for third-party Anthropic-compatible providers."""
        result = dict(anthropic_request)

        # Remove unsupported fields
        for field in self._REMOVE_FIELDS:
            result.pop(field, None)

        # Convert system from array to string
        system = result.get("system")
        if isinstance(system, list):
            result["system"] = "\n".join(
                block.get("text", "") for block in system if isinstance(block, dict)
            )

        # Ensure temperature is float
        if "temperature" in result:
            result["temperature"] = float(result["temperature"])

        return result

    def transform_response(self, provider_response: dict[str, Any]) -> dict[str, Any]:
        """Return response unchanged - provider returns Anthropic format."""
        return provider_response
