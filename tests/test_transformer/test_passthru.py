"""Tests for the Anthropic passthrough transformer."""

from lccg.transformer.anthropic_passthru import AnthropicPassthruTransformer


class TestAnthropicPassthruTransformer:
    def setup_method(self):
        self.transformer = AnthropicPassthruTransformer()

    def test_request_passthrough(self):
        request = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        result = self.transformer.transform_request(request)
        assert result == request

    def test_response_passthrough(self):
        response = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "model": "MiniMax-M2.1",
            "content": [{"type": "text", "text": "Hi there!"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        result = self.transformer.transform_response(response)
        assert result == response

    def test_request_with_tools(self):
        request = {
            "model": "MiniMax-M2.1",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": "What's the weather?"}],
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
        assert result == request

    def test_request_with_thinking(self):
        request = {
            "model": "MiniMax-M2.1",
            "max_tokens": 16000,
            "messages": [{"role": "user", "content": "Think about this"}],
            "thinking": {"type": "enabled", "budget_tokens": 10000},
        }
        result = self.transformer.transform_request(request)
        assert result == request
