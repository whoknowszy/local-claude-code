"""Anthropic ↔ OpenAI format conversion transformer."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator

import structlog

from lccg.transformer.base import BaseTransformer

logger = structlog.get_logger()

# Stop reason mapping: OpenAI → Anthropic
_STOP_REASON_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "stop_sequence",
    "stop_sequence": "stop_sequence",
}


class OpenAIConvertTransformer(BaseTransformer):
    """Converts between Anthropic Messages API and OpenAI Chat Completions formats."""

    # --- Request: Anthropic → OpenAI ---

    def transform_request(self, anthropic_request: dict[str, Any]) -> dict[str, Any]:
        """Convert Anthropic request to OpenAI Chat Completions format."""
        result: dict[str, Any] = {}
        messages: list[dict[str, Any]] = []

        # Model
        result["model"] = anthropic_request.get("model", "")

        # System → system message
        system = anthropic_request.get("system")
        if system:
            if isinstance(system, str):
                messages.append({"role": "system", "content": system})
            elif isinstance(system, list):
                text = "\n".join(
                    b.get("text", "") for b in system if isinstance(b, dict) and b.get("type") == "text"
                )
                if text:
                    messages.append({"role": "system", "content": text})

        # Messages
        for msg in anthropic_request.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "user":
                self._convert_user_message(msg, messages)
            elif role == "assistant":
                self._convert_assistant_message(msg, messages)
            else:
                messages.append({"role": role, "content": content if isinstance(content, str) else ""})

        result["messages"] = messages

        # Max tokens
        if "max_tokens" in anthropic_request:
            result["max_tokens"] = anthropic_request["max_tokens"]

        # Temperature
        if "temperature" in anthropic_request:
            result["temperature"] = float(anthropic_request["temperature"])

        # Tools
        tools = anthropic_request.get("tools")
        if tools:
            result["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {}),
                    },
                }
                for t in tools
            ]

        # Tool choice
        tool_choice = anthropic_request.get("tool_choice")
        if tool_choice:
            if isinstance(tool_choice, dict):
                if tool_choice.get("type") == "tool":
                    result["tool_choice"] = {
                        "type": "function",
                        "function": {"name": tool_choice.get("name", "")},
                    }
                elif tool_choice.get("type") in ("auto", "any"):
                    result["tool_choice"] = tool_choice["type"]
            elif isinstance(tool_choice, str):
                result["tool_choice"] = tool_choice

        # Thinking → enable_thinking
        thinking = anthropic_request.get("thinking")
        if thinking and thinking.get("type") == "enabled":
            result["enable_thinking"] = True
            if thinking.get("budget_tokens"):
                result["reasoning_effort"] = "high"

        # Stream
        if anthropic_request.get("stream"):
            result["stream"] = True

        # Remove Anthropic-specific fields (they shouldn't propagate)
        for field in ("metadata", "output_config", "system", "thinking"):
            # Already handled above, just ensure they don't leak
            pass

        return result

    def _convert_user_message(self, msg: dict[str, Any], messages: list[dict[str, Any]]) -> None:
        """Convert a user message, handling tool_result and content blocks."""
        content = msg.get("content", "")

        if isinstance(content, str):
            messages.append({"role": "user", "content": content})
            return

        if not isinstance(content, list):
            messages.append({"role": "user", "content": ""})
            return

        # Separate tool_result blocks from text/image blocks
        text_parts: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                continue

            block_type = block.get("type", "")

            if block_type == "tool_result":
                # → role: "tool" message
                tool_msg: dict[str, Any] = {
                    "role": "tool",
                    "tool_call_id": block.get("tool_use_id", ""),
                }
                tool_content = block.get("content", "")
                if isinstance(tool_content, str):
                    tool_msg["content"] = tool_content
                elif isinstance(tool_content, list):
                    tool_msg["content"] = "\n".join(
                        b.get("text", "") for b in tool_content if isinstance(b, dict) and b.get("type") == "text"
                    )
                else:
                    tool_msg["content"] = ""
                messages.append(tool_msg)
            elif block_type == "text":
                text_parts.append({"type": "text", "text": block.get("text", "")})
            elif block_type == "image":
                source = block.get("source", {})
                if source.get("type") == "base64":
                    media_type = source.get("media_type", "image/png")
                    data = source.get("data", "")
                    text_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{data}"},
                    })
                elif source.get("type") == "url":
                    text_parts.append({
                        "type": "image_url",
                        "image_url": {"url": source.get("url", "")},
                    })

        if text_parts:
            # If only one text part, simplify to string
            if len(text_parts) == 1 and text_parts[0].get("type") == "text":
                messages.append({"role": "user", "content": text_parts[0]["text"]})
            else:
                messages.append({"role": "user", "content": text_parts})

    def _convert_assistant_message(self, msg: dict[str, Any], messages: list[dict[str, Any]]) -> None:
        """Convert an assistant message, handling text, tool_use, and thinking blocks."""
        content = msg.get("content", "")

        if isinstance(content, str):
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
            messages.append(assistant_msg)
            return

        if not isinstance(content, list):
            messages.append({"role": "assistant", "content": ""})
            return

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        thinking_content: str | None = None

        for block in content:
            if not isinstance(block, dict):
                continue

            block_type = block.get("type", "")

            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append({
                    "id": block.get("id", f"call_{uuid.uuid4().hex[:24]}"),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                    },
                })
            elif block_type == "thinking":
                thinking_content = block.get("thinking", "")

        assistant_msg: dict[str, Any] = {"role": "assistant"}

        if thinking_content:
            assistant_msg["reasoning_content"] = thinking_content

        assistant_msg["content"] = "\n".join(text_parts) if text_parts else None

        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls

        messages.append(assistant_msg)

    # --- Response: OpenAI → Anthropic (non-streaming) ---

    def transform_response(self, provider_response: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAI response to Anthropic format."""
        choice = provider_response.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Build content blocks
        content: list[dict[str, Any]] = []

        # Thinking/reasoning
        reasoning = message.get("reasoning_content")
        if reasoning:
            content.append({
                "type": "thinking",
                "thinking": reasoning,
                "signature": f"sig_{int(time.time())}",
            })

        # Text content
        text = message.get("content")
        if text:
            content.append({"type": "text", "text": text})

        # Tool calls
        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            input_raw = func.get("arguments", "{}")
            try:
                input_parsed = json.loads(input_raw)
            except (json.JSONDecodeError, TypeError):
                input_parsed = {"raw": input_raw}

            content.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                "name": func.get("name", ""),
                "input": input_parsed,
            })

        if not content:
            content.append({"type": "text", "text": ""})

        # Stop reason
        openai_reason = choice.get("finish_reason")
        stop_reason = _STOP_REASON_MAP.get(openai_reason, "end_turn") if openai_reason else None

        # Usage
        usage_data = provider_response.get("usage", {})
        usage = {
            "input_tokens": usage_data.get("prompt_tokens", 0),
            "output_tokens": usage_data.get("completion_tokens", 0),
        }

        return {
            "id": provider_response.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
            "type": "message",
            "role": "assistant",
            "model": provider_response.get("model", ""),
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": usage,
        }

    # --- Stream: OpenAI SSE → Anthropic SSE ---

    async def transform_stream(self, stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        """Convert OpenAI SSE stream to Anthropic SSE event stream."""
        state = _StreamState()

        buffer = ""
        async for chunk in stream:
            buffer += chunk.decode("utf-8", errors="replace")
            lines = buffer.split("\n")
            buffer = lines.pop()  # keep last incomplete line

            for line in lines:
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue

                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    # Emit final events
                    for event in state.finish():
                        yield event
                    continue

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                for event in state.process_chunk(data):
                    yield event

        # If stream ends without [DONE]
        if state.has_content() and not state.is_finished():
            for event in state.finish():
                yield event


class _StreamState:
    """State machine for converting OpenAI SSE chunks to Anthropic SSE events."""

    def __init__(self) -> None:
        self.message_id = f"msg_{uuid.uuid4().hex[:24]}"
        self.model = ""
        self.content_index = 0
        self.has_sent_message_start = False
        self.current_block_type: str | None = None  # "thinking" | "text" | "tool_use"
        self.current_block_index = -1
        self.thinking_content = ""
        self.is_thinking_done = False
        self.text_started = False
        self.tool_calls: dict[int, dict[str, Any]] = {}  # openai_index → {id, name, args}
        self.tool_call_to_block: dict[int, int] = {}  # openai_index → content_block_index
        self.stop_reason: str | None = None
        self.usage: dict[str, int] = {}
        self._finished = False

    def has_content(self) -> bool:
        return self.has_sent_message_start

    def is_finished(self) -> bool:
        return self._finished

    def _make_event(self, event_type: str, data: dict[str, Any]) -> bytes:
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()

    def _next_index(self) -> int:
        idx = self.content_index
        self.content_index += 1
        return idx

    def process_chunk(self, data: dict[str, Any]) -> list[bytes]:
        """Process an OpenAI SSE chunk and yield Anthropic SSE events."""
        events: list[bytes] = []
        choice = data.get("choices", [{}])[0] if data.get("choices") else {}
        delta = choice.get("delta", {})

        # Update model
        if data.get("model"):
            self.model = data["model"]

        # Send message_start on first chunk
        if not self.has_sent_message_start:
            self.has_sent_message_start = True
            events.append(self._make_event("message_start", {
                "type": "message_start",
                "message": {
                    "id": self.message_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": self.model,
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            }))

        # Thinking (reasoning_content)
        reasoning = delta.get("reasoning_content")
        if reasoning:
            self.thinking_content += reasoning
            if self.current_block_type != "thinking":
                # Close previous block
                if self.current_block_type:
                    events.append(self._make_event("content_block_stop", {
                        "type": "content_block_stop",
                        "index": self.current_block_index,
                    }))
                self.current_block_index = self._next_index()
                self.current_block_type = "thinking"
                events.append(self._make_event("content_block_start", {
                    "type": "content_block_start",
                    "index": self.current_block_index,
                    "content_block": {"type": "thinking", "thinking": ""},
                }))
            events.append(self._make_event("content_block_delta", {
                "type": "content_block_delta",
                "index": self.current_block_index,
                "delta": {"type": "thinking_delta", "thinking": reasoning},
            }))
            return events

        # If thinking was active and now content starts, close thinking block
        if self.current_block_type == "thinking" and not self.is_thinking_done:
            self.is_thinking_done = True
            # Send signature delta
            events.append(self._make_event("content_block_delta", {
                "type": "content_block_delta",
                "index": self.current_block_index,
                "delta": {"type": "signature_delta", "signature": f"sig_{int(time.time())}"},
            }))
            events.append(self._make_event("content_block_stop", {
                "type": "content_block_stop",
                "index": self.current_block_index,
            }))
            self.current_block_type = None

        # Text content
        text = delta.get("content")
        if text:
            if self.current_block_type != "text":
                if self.current_block_type:
                    events.append(self._make_event("content_block_stop", {
                        "type": "content_block_stop",
                        "index": self.current_block_index,
                    }))
                self.current_block_index = self._next_index()
                self.current_block_type = "text"
                events.append(self._make_event("content_block_start", {
                    "type": "content_block_start",
                    "index": self.current_block_index,
                    "content_block": {"type": "text", "text": ""},
                }))
            events.append(self._make_event("content_block_delta", {
                "type": "content_block_delta",
                "index": self.current_block_index,
                "delta": {"type": "text_delta", "text": text},
            }))
            return events

        # Tool calls
        tool_calls = delta.get("tool_calls", [])
        for tc in tool_calls:
            tc_index = tc.get("index", 0)
            func = tc.get("function", {})

            # First time seeing this tool call
            if tc_index not in self.tool_calls:
                self.tool_calls[tc_index] = {
                    "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                    "name": func.get("name", ""),
                    "args": "",
                }
                # Close previous block
                if self.current_block_type:
                    events.append(self._make_event("content_block_stop", {
                        "type": "content_block_stop",
                        "index": self.current_block_index,
                    }))
                block_idx = self._next_index()
                self.tool_call_to_block[tc_index] = block_idx
                self.current_block_type = "tool_use"
                self.current_block_index = block_idx
                events.append(self._make_event("content_block_start", {
                    "type": "content_block_start",
                    "index": block_idx,
                    "content_block": {
                        "type": "tool_use",
                        "id": self.tool_calls[tc_index]["id"],
                        "name": self.tool_calls[tc_index]["name"],
                        "input": {},
                    },
                }))
            else:
                # Update name if provided
                if func.get("name"):
                    self.tool_calls[tc_index]["name"] = func["name"]

            # Arguments delta
            args_fragment = func.get("arguments", "")
            if args_fragment:
                self.tool_calls[tc_index]["args"] += args_fragment
                block_idx = self.tool_call_to_block[tc_index]
                events.append(self._make_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": block_idx,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": args_fragment,
                    },
                }))

        # Finish reason
        finish_reason = choice.get("finish_reason")
        if finish_reason:
            self.stop_reason = _STOP_REASON_MAP.get(finish_reason, "end_turn")

        # Always capture usage when present (may arrive in a separate chunk from finish_reason)
        if data.get("usage"):
            u = data["usage"]
            self.usage = {
                "input_tokens": u.get("prompt_tokens", 0),
                "output_tokens": u.get("completion_tokens", 0),
            }

        return events

    def finish(self) -> list[bytes]:
        """Emit final events to close the stream."""
        self._finished = True
        events: list[bytes] = []

        # If we never sent message_start, nothing to close
        if not self.has_sent_message_start:
            return events

        # Close current block
        if self.current_block_type:
            events.append(self._make_event("content_block_stop", {
                "type": "content_block_stop",
                "index": self.current_block_index,
            }))

        # message_delta with stop_reason
        events.append(self._make_event("message_delta", {
            "type": "message_delta",
            "delta": {
                "stop_reason": self.stop_reason or "end_turn",
                "stop_sequence": None,
            },
            "usage": self.usage or {"input_tokens": 0, "output_tokens": 0},
        }))

        # message_stop
        events.append(self._make_event("message_stop", {
            "type": "message_stop",
        }))

        return events
