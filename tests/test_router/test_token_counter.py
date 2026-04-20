"""Tests for the token counter utility."""

from lccg.router.token_counter import count_tokens


class TestTokenCounter:
    def test_count_simple_message(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "Hello world"}],
        }
        tokens = count_tokens(request)
        assert tokens > 0
        assert tokens < 10  # "Hello world" is ~2 tokens

    def test_count_with_system(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "system": "You are a helpful assistant with extensive knowledge.",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        tokens = count_tokens(request)
        # System prompt adds tokens
        assert tokens > 5

    def test_count_with_system_array(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "system": [
                {"type": "text", "text": "Part one of system prompt."},
                {"type": "text", "text": "Part two of system prompt."},
            ],
            "messages": [{"role": "user", "content": "Hi"}],
        }
        tokens = count_tokens(request)
        assert tokens > 5

    def test_count_with_tools(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "What's the weather?"}],
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get the weather for a location",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                    },
                }
            ],
        }
        tokens = count_tokens(request)
        # Tools add significant tokens
        assert tokens > 15

    def test_count_array_content(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Hello"},
                        {"type": "text", "text": "World"},
                    ],
                }
            ],
        }
        tokens = count_tokens(request)
        assert tokens > 0

    def test_count_with_thinking(self):
        request = {
            "model": "gpt-4o",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "This is a long thinking block with many words.",
                        },
                        {"type": "text", "text": "The answer is 42."},
                    ],
                }
            ],
        }
        tokens = count_tokens(request)
        assert tokens > 5
