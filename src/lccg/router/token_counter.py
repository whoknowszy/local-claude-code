"""Token counting utility for routing decisions."""

from __future__ import annotations

import json
from typing import Any

import tiktoken

# Cache encoder at module level for performance
_encoder = tiktoken.get_encoding("cl100k_base")


def count_tokens(request: dict[str, Any]) -> int:
    """Count tokens in an Anthropic-format request using tiktoken cl100k_base.

    This is an approximation (Claude uses a different tokenizer), but is sufficient
    for routing threshold decisions like long_context switching.
    """
    token_count = 0

    # System prompt
    system = request.get("system")
    if system:
        if isinstance(system, str):
            token_count += len(_encoder.encode(system))
        elif isinstance(system, list):
            for block in system:
                if isinstance(block, dict) and block.get("type") == "text":
                    token_count += len(_encoder.encode(block.get("text", "")))

    # Messages
    for msg in request.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str):
            token_count += len(_encoder.encode(content))
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    token_count += len(_encoder.encode(block.get("text", "")))
                elif btype == "tool_use":
                    token_count += len(_encoder.encode(json.dumps(block.get("input", {}))))
                elif btype == "tool_result":
                    tc = block.get("content", "")
                    if isinstance(tc, str):
                        token_count += len(_encoder.encode(tc))
                    elif isinstance(tc, list):
                        for b in tc:
                            if isinstance(b, dict) and b.get("type") == "text":
                                token_count += len(_encoder.encode(b.get("text", "")))
                elif btype == "thinking":
                    token_count += len(_encoder.encode(block.get("thinking", "")))
                elif btype == "image":
                    token_count += 100  # rough estimate for image tokens

    # Tools
    tools = request.get("tools")
    if tools:
        token_count += len(_encoder.encode(json.dumps(tools)))

    return token_count
