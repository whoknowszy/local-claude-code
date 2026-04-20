"""Tests for configuration loading and schema validation."""

import os
from pathlib import Path

import pytest
import yaml

from lccg.config.loader import _resolve_env_vars, load_config
from lccg.config.schema import ProviderType


class TestEnvVarResolution:
    def test_resolve_dollar_brace_var(self):
        os.environ["TEST_API_KEY"] = "sk-test-123"
        result = _resolve_env_vars("${TEST_API_KEY}")
        assert result == "sk-test-123"
        del os.environ["TEST_API_KEY"]

    def test_resolve_dollar_var(self):
        os.environ["TEST_VAR"] = "hello"
        result = _resolve_env_vars("$TEST_VAR")
        assert result == "hello"
        del os.environ["TEST_VAR"]

    def test_undefined_var_kept_as_is(self):
        result = _resolve_env_vars("${UNDEFINED_VAR_XYZ}")
        assert result == "${UNDEFINED_VAR_XYZ}"

    def test_resolve_in_nested_dict(self):
        from lccg.config.loader import _resolve_env_in_dict

        os.environ["TEST_NESTED"] = "value123"
        data = {"a": {"b": "${TEST_NESTED}"}, "c": ["${TEST_NESTED}"]}
        result = _resolve_env_in_dict(data)
        assert result == {"a": {"b": "value123"}, "c": ["value123"]}
        del os.environ["TEST_NESTED"]


class TestConfigLoading:
    def test_load_valid_config(self, tmp_path: Path):
        config_data = {
            "server": {"host": "0.0.0.0", "port": 9999},
            "providers": [
                {
                    "name": "test-provider",
                    "type": "anthropic",
                    "base_url": "https://api.example.com/v1/messages",
                    "api_key": "sk-test",
                    "models": ["model-1"],
                }
            ],
            "router": {"default": "test-provider,model-1"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(config_file)

        assert config.server.host == "0.0.0.0"
        assert config.server.port == 9999
        assert len(config.providers) == 1
        assert config.providers[0].name == "test-provider"
        assert config.providers[0].type == ProviderType.ANTHROPIC
        assert config.providers[0].models == ["model-1"]
        assert config.router.default == "test-provider,model-1"

    def test_load_config_with_env_vars(self, tmp_path: Path):
        os.environ["LCCG_TEST_KEY"] = "sk-from-env"
        config_data = {
            "providers": [
                {
                    "name": "env-provider",
                    "type": "anthropic",
                    "base_url": "https://api.example.com/v1/messages",
                    "api_key": "${LCCG_TEST_KEY}",
                    "models": ["model-1"],
                }
            ],
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(config_file)
        assert config.providers[0].api_key == "sk-from-env"
        del os.environ["LCCG_TEST_KEY"]

    def test_load_config_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config("/nonexistent/path/config.yaml")

    def test_load_config_defaults(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("{}")

        config = load_config(config_file)
        assert config.server.host == "127.0.0.1"
        assert config.server.port == 8765
        assert config.server.api_key is None
        assert config.providers == []
        assert config.router.default is None
