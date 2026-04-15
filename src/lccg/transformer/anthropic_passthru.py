"""Anthropic passthrough transformer with field cleanup for third-party providers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from lccg.transformer.base import BaseTransformer


def _is_openai_format(response: dict[str, Any]) -> bool:
    """Detect if response is in OpenAI format rather than Anthropic format.

    OpenAI format: has 'choices' field, no 'content' list field
    Anthropic format: has 'content' (list) and 'type' == 'message'
    """
    # OpenAI responses have 'choices' and typically no 'content' at top level
    # or 'content' is not a list (Anthropic content is always a list of blocks)
    if "choices" in response:
        content = response.get("content")
        # Anthropic format has content as a list of blocks
        if not isinstance(content, list):
            return True
        # If has 'choices' but also has 'type': 'message', it's likely Anthropic
        if response.get("type") != "message":
            return True
    return False


class AnthropicPassthruTransformer(BaseTransformer):
    """Pass-through transformer for providers that natively support Anthropic API format.

    Cleans up fields that third-party providers may not support:
    - system: converts array format to string
    - output_config: removed (json_schema not universally supported)
    - metadata: removed (Anthropic-specific)
    - temperature: ensures float

    Also auto-detects and converts OpenAI format responses if provider returns wrong format.
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
        """Return response unchanged, or auto-convert if OpenAI format detected."""
        # Detect OpenAI format response (has 'choices' field, not Anthropic format)
        if _is_openai_format(provider_response):
            import structlog

            logger = structlog.get_logger("gateway")
            logger.warning(
                "gateway.format_mismatch",
                msg="Provider configured as 'anthropic' but returned OpenAI format. "
                "Consider changing provider type to 'openai' in config.",
            )
            from lccg.transformer.openai_convert import OpenAIConvertTransformer

            converter = OpenAIConvertTransformer()
            return converter.transform_response(provider_response)
        return provider_response

    async def transform_stream(self, stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        """Pass-through stream, or auto-convert if OpenAI SSE format detected."""
        import json

        buffer = ""
        format_detected = False
        is_openai_stream = False
        openai_converter: Any = None

        async for chunk in stream:
            chunk_str = chunk.decode("utf-8", errors="replace")

            # Detect format from first data chunk
            if not format_detected:
                buffer += chunk_str

                # Look for first data line to detect format
                for line in buffer.split("\n"):
                    line = line.strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        data_str = line[6:].strip()
                        try:
                            data = json.loads(data_str)
                            # OpenAI SSE has 'choices' in data chunks
                            if "choices" in data:
                                is_openai_stream = True
                                import structlog

                                logger = structlog.get_logger("gateway")
                                logger.warning(
                                    "gateway.format_mismatch",
                                    msg="Provider configured as 'anthropic' but streaming "
                                    "OpenAI format. Consider changing provider type to "
                                    "'openai' in config.",
                                )
                                from lccg.transformer.openai_convert import (
                                    OpenAIConvertTransformer,
                                )

                                openai_converter = OpenAIConvertTransformer()
                            format_detected = True
                            break
                        except json.JSONDecodeError:
                            continue
                    elif line.startswith("event: "):
                        # Anthropic SSE uses event: prefix
                        format_detected = True
                        is_openai_stream = False
                        break

                if format_detected:
                    if is_openai_stream and openai_converter is not None:
                        # Re-wrap buffered content as async iterator and delegate
                        async def _rewrap_stream(
                            initial: str, remaining: AsyncIterator[bytes]
                        ) -> AsyncIterator[bytes]:
                            yield initial.encode("utf-8")
                            async for c in remaining:
                                yield c

                        async for converted in openai_converter.transform_stream(
                            _rewrap_stream(buffer, stream)
                        ):
                            yield converted
                        return
                    else:
                        # Anthropic format - yield buffered content and continue pass-through
                        yield buffer.encode("utf-8")
                        buffer = ""
                else:
                    # Not enough data yet, continue buffering
                    continue
            else:
                # Format already detected as Anthropic, pass-through
                yield chunk

        # If stream ended while still buffering (no format detected), yield buffer
        if buffer:
            yield buffer.encode("utf-8")
