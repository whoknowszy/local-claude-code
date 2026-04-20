"""Tests for the Anthropic ↔ OpenAI conversion transformer."""

from __future__ import annotations

import json

import pytest

from lccg.transformer.openai_convert import OpenAIConvertTransformer


class TestTransformRequest:
    def setup_method(self):
        self.transformer = OpenAIConvertTransformer()

    def test_simple_text_request(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = self.transformer.transform_request(request)
        assert result["model"] == "gpt-4o"
        assert result["max_tokens"] == 1024
        assert result["messages"] == [{"role": "user", "content": "Hello"}]

    def test_system_string_to_message(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "system": "You are helpful.",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        result = self.transformer.transform_request(request)
        assert result["messages"][0] == {"role": "system", "content": "You are helpful."}
        assert result["messages"][1] == {"role": "user", "content": "Hi"}

    def test_system_array_to_message(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "system": [
                {"type": "text", "text": "Part 1"},
                {"type": "text", "text": "Part 2"},
            ],
            "messages": [{"role": "user", "content": "Hi"}],
        }
        result = self.transformer.transform_request(request)
        assert result["messages"][0] == {"role": "system", "content": "Part 1\nPart 2"}

    def test_tool_result_to_tool_message(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "toolu_123", "content": "result text"},
                    ],
                }
            ],
        }
        result = self.transformer.transform_request(request)
        assert result["messages"][0] == {
            "role": "tool",
            "tool_call_id": "toolu_123",
            "content": "result text",
        }

    def test_tool_use_to_tool_calls(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me check."},
                        {
                            "type": "tool_use",
                            "id": "toolu_abc",
                            "name": "get_weather",
                            "input": {"location": "Beijing"},
                        },
                    ],
                }
            ],
        }
        result = self.transformer.transform_request(request)
        msg = result["messages"][0]
        assert msg["role"] == "assistant"
        assert msg["content"] == "Let me check."
        assert len(msg["tool_calls"]) == 1
        assert msg["tool_calls"][0]["function"]["name"] == "get_weather"
        assert json.loads(msg["tool_calls"][0]["function"]["arguments"]) == {"location": "Beijing"}

    def test_tools_input_schema_to_parameters(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [],
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                    },
                }
            ],
        }
        result = self.transformer.transform_request(request)
        assert len(result["tools"]) == 1
        assert result["tools"][0]["type"] == "function"
        assert result["tools"][0]["function"]["name"] == "get_weather"
        assert result["tools"][0]["function"]["parameters"]["type"] == "object"

    def test_tool_choice_mapping(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [],
            "tool_choice": {"type": "tool", "name": "get_weather"},
        }
        result = self.transformer.transform_request(request)
        assert result["tool_choice"] == {
            "type": "function",
            "function": {"name": "get_weather"},
        }

    def test_tool_choice_auto(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [],
            "tool_choice": "auto",
        }
        result = self.transformer.transform_request(request)
        assert result["tool_choice"] == "auto"

    def test_thinking_to_enable_thinking(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [],
            "thinking": {"type": "enabled", "budget_tokens": 5000},
        }
        result = self.transformer.transform_request(request)
        assert result["enable_thinking"] is True

    def test_thinking_disabled_when_tool_call_history_lacks_reasoning(self):
        request = {
            "model": "kimi-k2.5",
            "max_tokens": 100,
            "thinking": {"type": "enabled", "budget_tokens": 5000},
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_abc",
                            "name": "read_file",
                            "input": {"path": "app.py"},
                        },
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_abc",
                            "content": "file contents",
                        },
                    ],
                },
            ],
        }

        result = self.transformer.transform_request(request)

        assert "enable_thinking" not in result
        assert "reasoning_effort" not in result

    def test_metadata_fields_removed(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "Hi"}],
            "metadata": {"user_id": "abc"},
            "output_config": {"format": {"type": "json_schema"}},
        }
        result = self.transformer.transform_request(request)
        assert "metadata" not in result
        assert "output_config" not in result

    def test_temperature_is_float(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "temperature": 1,
            "messages": [],
        }
        result = self.transformer.transform_request(request)
        assert result["temperature"] == 1.0


class TestTransformResponse:
    def setup_method(self):
        self.transformer = OpenAIConvertTransformer()

    def test_text_response(self):
        response = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        result = self.transformer.transform_response(response)
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["content"] == [{"type": "text", "text": "Hello!"}]
        assert result["stop_reason"] == "end_turn"
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 5

    def test_tool_calls_response(self):
        response = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location":"Beijing"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 15},
        }
        result = self.transformer.transform_response(response)
        assert result["stop_reason"] == "tool_use"
        assert len(result["content"]) == 1
        block = result["content"][0]
        assert block["type"] == "tool_use"
        assert block["name"] == "get_weather"
        assert block["input"] == {"location": "Beijing"}

    def test_reasoning_content_response(self):
        response = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "The answer is 42.",
                        "reasoning_content": "Let me think...",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        result = self.transformer.transform_response(response)
        assert result["content"][0]["type"] == "thinking"
        assert result["content"][0]["thinking"] == "Let me think..."
        assert result["content"][1]["type"] == "text"
        assert result["content"][1]["text"] == "The answer is 42."

    def test_stop_reason_mapping(self):
        cases = [
            ("stop", "end_turn"),
            ("length", "max_tokens"),
            ("tool_calls", "tool_use"),
            ("content_filter", "stop_sequence"),
        ]
        for openai_reason, expected in cases:
            response = {
                "id": "chatcmpl-123",
                "model": "gpt-4o",
                "choices": [
                    {"message": {"role": "assistant", "content": "Hi"}, "finish_reason": openai_reason}
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            }
            result = self.transformer.transform_response(response)
            assert result["stop_reason"] == expected, f"Expected {expected} for {openai_reason}"


class TestTransformStream:
    def setup_method(self):
        self.transformer = OpenAIConvertTransformer()

    def _make_sse_chunks(self, data_list: list[dict | str]) -> list[bytes]:
        """Create SSE byte chunks from a list of data objects or 'DONE'."""
        chunks = []
        for item in data_list:
            if item == "DONE":
                chunks.append(b"data: [DONE]\n\n")
            else:
                chunks.append(f"data: {json.dumps(item)}\n\n".encode())
        return chunks

    async def _collect_events(self, chunks: list[bytes]) -> list[dict]:
        """Run chunks through transformer and parse resulting events."""

        async def fake_stream():
            for chunk in chunks:
                yield chunk

        events = []
        async for chunk in self.transformer.transform_stream(fake_stream()):
            text = chunk.decode("utf-8")
            for line in text.strip().split("\n"):
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
                    events.append({"event": event_type, "data": data})
        return events

    @pytest.mark.asyncio
    async def test_text_only_stream(self):
        chunks = self._make_sse_chunks([
            {"choices": [{"delta": {"role": "assistant", "content": "Hello"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": " world"}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 10}},
            "DONE",
        ])
        events = await self._collect_events(chunks)
        event_types = [e["event"] for e in events]
        assert event_types[0] == "message_start"
        assert "content_block_start" in event_types
        assert "content_block_delta" in event_types
        assert "content_block_stop" in event_types
        assert "message_delta" in event_types
        assert "message_stop" in event_types

    @pytest.mark.asyncio
    async def test_tool_calls_stream(self):
        arg1 = '{"loc'
        arg2 = 'ation":"Beijing"}'
        chunks = self._make_sse_chunks([
            {"choices": [{"delta": {"role": "assistant", "content": None, "tool_calls": [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": ""}}]}, "finish_reason": None}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": arg1}}]}, "finish_reason": None}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": arg2}}]}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 10, "completion_tokens": 20}},
            "DONE",
        ])
        events = await self._collect_events(chunks)
        event_types = [e["event"] for e in events]

        # Should have: message_start, content_block_start(tool_use), 2x content_block_delta(input_json), content_block_stop, message_delta, message_stop
        assert event_types[0] == "message_start"

        # Find the tool_use content_block_start
        tool_starts = [e for e in events if e["event"] == "content_block_start" and e["data"]["content_block"]["type"] == "tool_use"]
        assert len(tool_starts) == 1
        assert tool_starts[0]["data"]["content_block"]["name"] == "get_weather"

        # Find input_json deltas
        json_deltas = [e for e in events if e["event"] == "content_block_delta" and e["data"]["delta"]["type"] == "input_json_delta"]
        assert len(json_deltas) == 2

        assert events[-1]["event"] == "message_stop"

    @pytest.mark.asyncio
    async def test_thinking_stream(self):
        chunks = self._make_sse_chunks([
            {"choices": [{"delta": {"role": "assistant", "reasoning_content": "Let me"}, "finish_reason": None}]},
            {"choices": [{"delta": {"reasoning_content": " think..."}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "The answer"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": " is 42."}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 15}},
            "DONE",
        ])
        events = await self._collect_events(chunks)

        # Should have thinking block followed by text block
        thinking_starts = [e for e in events if e["event"] == "content_block_start" and e["data"]["content_block"]["type"] == "thinking"]
        text_starts = [e for e in events if e["event"] == "content_block_start" and e["data"]["content_block"]["type"] == "text"]
        assert len(thinking_starts) == 1
        assert len(text_starts) == 1

        # Thinking block should have signature delta
        sig_deltas = [e for e in events if e["event"] == "content_block_delta" and e["data"]["delta"]["type"] == "signature_delta"]
        assert len(sig_deltas) == 1

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        chunks = self._make_sse_chunks(["DONE"])
        events = await self._collect_events(chunks)
        # Should have no events for empty stream with [DONE] only
        assert len(events) == 0
