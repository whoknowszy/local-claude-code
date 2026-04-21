"""Tests for OpenAI-compatible provider payload handling."""

from __future__ import annotations

import httpx
import pytest

from lccg.config.schema import ProviderConfig, ProviderType
from lccg.provider.openai_provider import (
    OpenAIProvider,
    collapse_tool_call_history_for_retry,
    disable_reasoning_for_retry,
    is_missing_reasoning_content_error,
    sanitize_reasoning_tool_call_payload,
)


def test_sanitize_reasoning_tool_call_payload_backfills_missing_reasoning_content():
    payload = {
        "model": "kimi-k2.5",
        "enable_thinking": True,
        "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Read a file."},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "toolu_abc",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
        ],
    }

    sanitized = sanitize_reasoning_tool_call_payload(payload)

    msg = sanitized["messages"][2]
    assert msg["reasoning_content"]
    assert list(msg).index("reasoning_content") < list(msg).index("tool_calls")


def test_sanitize_reasoning_tool_call_payload_preserves_existing_reasoning_content():
    payload = {
        "model": "kimi-k2.5",
        "enable_thinking": True,
        "messages": [
            {
                "role": "assistant",
                "reasoning_content": "I need to inspect the file.",
                "content": None,
                "tool_calls": [
                    {
                        "id": "toolu_abc",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
        ],
    }

    sanitized = sanitize_reasoning_tool_call_payload(payload)

    assert sanitized["messages"][0]["reasoning_content"] == "I need to inspect the file."


def test_sanitize_reasoning_tool_call_payload_ignores_non_thinking_requests():
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "toolu_abc",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
        ],
    }

    sanitized = sanitize_reasoning_tool_call_payload(payload)

    assert "reasoning_content" not in sanitized["messages"][0]


def test_is_missing_reasoning_content_error_detects_moonshot_400():
    body = (
        '{"error":{"message":"thinking is enabled but reasoning_content is missing in '
        'assistant tool call message at index 2","type":"invalid_request_error"}}'
    )

    assert is_missing_reasoning_content_error(400, body) is True


def test_is_missing_reasoning_content_error_ignores_other_errors():
    assert is_missing_reasoning_content_error(400, '{"error":{"message":"bad key"}}') is False
    assert is_missing_reasoning_content_error(500, "reasoning_content is missing") is False


def test_disable_reasoning_for_retry_removes_thinking_flags():
    payload = {
        "model": "kimi-k2.5",
        "enable_thinking": True,
        "reasoning_effort": "high",
        "messages": [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "reasoning_content": "placeholder",
                "content": None,
                "tool_calls": [
                    {
                        "id": "toolu_abc",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
        ],
    }

    retry_payload = disable_reasoning_for_retry(payload)

    assert retry_payload["enable_thinking"] is False
    assert retry_payload["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in retry_payload
    assert "reasoning_content" not in retry_payload["messages"][1]


def test_collapse_tool_call_history_for_retry_converts_tool_calls_to_text():
    payload = {
        "model": "kimi-k2.5",
        "messages": [
            {"role": "user", "content": "inspect app.py"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Read", "arguments": '{"file_path":"app.py"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "print('hello')"},
            {"role": "user", "content": "continue"},
        ],
    }

    retry_payload = collapse_tool_call_history_for_retry(payload)

    assert [m["role"] for m in retry_payload["messages"]] == [
        "user",
        "assistant",
        "user",
        "user",
    ]
    assert "tool_calls" not in retry_payload["messages"][1]
    assert "reasoning_content" not in retry_payload["messages"][1]
    assert "Tool call history" in retry_payload["messages"][1]["content"]
    assert "Tool result" in retry_payload["messages"][2]["content"]


@pytest.mark.asyncio
async def test_send_request_retries_without_reasoning_on_missing_reasoning_error():
    class FakeClient:
        is_closed = False

        def __init__(self):
            self.payloads = []

        async def post(self, url, json):
            self.payloads.append(json)
            request = httpx.Request("POST", url)
            if len(self.payloads) == 1:
                return httpx.Response(
                    400,
                    content=(
                        b'{"error":{"message":"thinking is enabled but reasoning_content '
                        b'is missing in assistant tool call message at index 2"}}'
                    ),
                    request=request,
                )
            return httpx.Response(200, json={"ok": True}, request=request)

    provider = OpenAIProvider(
        ProviderConfig(
            name="opencode",
            type=ProviderType.OPENAI,
            base_url="https://opencode.ai/zen/go/v1/chat/completions",
        )
    )
    fake_client = FakeClient()
    provider._client = fake_client

    response = await provider.send_request(
        {
            "model": "kimi-k2.5",
            "enable_thinking": True,
            "reasoning_effort": "high",
            "messages": [{"role": "user", "content": "hi"}],
        }
    )

    assert response.status_code == 200
    assert len(fake_client.payloads) == 2
    assert fake_client.payloads[0]["enable_thinking"] is True
    assert fake_client.payloads[1]["enable_thinking"] is False
    assert fake_client.payloads[1]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in fake_client.payloads[1]
    assert all("tool_calls" not in msg for msg in fake_client.payloads[1]["messages"])


@pytest.mark.asyncio
async def test_stream_response_retries_without_reasoning_on_missing_reasoning_error():
    class FakeStreamContext:
        def __init__(self, response):
            self.response = response

        async def __aenter__(self):
            return self.response

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeStreamResponse:
        def __init__(self, status_code, body=b"", chunks=None):
            self.status_code = status_code
            self._body = body
            self._chunks = chunks or []
            self.headers = {}

        async def aread(self):
            return self._body

        async def aiter_bytes(self):
            for chunk in self._chunks:
                yield chunk

    class FakeClient:
        is_closed = False

        def __init__(self):
            self.payloads = []

        def stream(self, method, url, json):
            self.payloads.append(json)
            if len(self.payloads) == 1:
                return FakeStreamContext(
                    FakeStreamResponse(
                        400,
                        body=(
                            b'{"error":{"message":"thinking is enabled but reasoning_content '
                            b'is missing in assistant tool call message at index 2"}}'
                        ),
                    )
                )
            return FakeStreamContext(FakeStreamResponse(200, chunks=[b"data: ok\n\n"]))

    provider = OpenAIProvider(
        ProviderConfig(
            name="opencode",
            type=ProviderType.OPENAI,
            base_url="https://opencode.ai/zen/go/v1/chat/completions",
        )
    )
    fake_client = FakeClient()
    provider._client = fake_client

    chunks = [
        chunk
        async for chunk in provider.stream_response(
            {
                "model": "kimi-k2.5",
                "enable_thinking": True,
                "reasoning_effort": "high",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
    ]

    assert chunks == [b"data: ok\n\n"]
    assert len(fake_client.payloads) == 2
    assert fake_client.payloads[0]["enable_thinking"] is True
    assert fake_client.payloads[1]["enable_thinking"] is False
    assert fake_client.payloads[1]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in fake_client.payloads[1]
    assert all("tool_calls" not in msg for msg in fake_client.payloads[1]["messages"])
