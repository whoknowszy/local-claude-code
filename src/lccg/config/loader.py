"""Configuration loading from YAML files with environment variable substitution."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from lccg.config.schema import GatewayConfig

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _resolve_env_vars(value: str) -> str:
    """Replace ${VAR} and $VAR patterns with environment variable values."""
    def replacer(match: re.Match) -> str:
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, match.group(0))

    return _ENV_VAR_PATTERN.sub(replacer, value)


def _resolve_env_in_dict(data: Any) -> Any:
    """Recursively resolve environment variables in a data structure."""
    if isinstance(data, str):
        return _resolve_env_vars(data)
    if isinstance(data, dict):
        return {k: _resolve_env_in_dict(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_in_dict(item) for item in data]
    return data


def load_config(config_path: str | Path | None = None) -> GatewayConfig:
    """Load and validate gateway configuration from a YAML file.

    Args:
        config_path: Path to config file. Defaults to ~/.lccg/config.yaml

    Returns:
        Validated GatewayConfig instance.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If config file is not valid YAML.
        pydantic.ValidationError: If config fails validation.
    """
    if config_path is None:
        config_path = Path.home() / ".lccg" / "config.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        # Auto-create default config
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            default_config = GatewayConfig()
            save_config(default_config, config_path)
        except Exception:
            raise FileNotFoundError(
                f"Config file not found and could not create default: {config_path}\n"
                f"Please create it manually."
            )
        import structlog
        logger = structlog.get_logger()
        logger.info("config.created", path=str(config_path))

    with open(config_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f) or {}

    # Resolve environment variables in string values
    resolved_data = _resolve_env_in_dict(raw_data)

    # 移除 None 值，让 Pydantic 使用 default_factory 默认值
    resolved_data = {k: v for k, v in resolved_data.items() if v is not None}

    return GatewayConfig(**resolved_data)


def save_config(config: GatewayConfig, config_path: str | Path | None = None) -> None:
    """Save configuration to YAML file.

    Args:
        config: GatewayConfig instance to save.
        config_path: Path to config file. Defaults to ~/.lccg/config.yaml
    """
    if config_path is None:
        config_path = Path.home() / ".lccg" / "config.yaml"
    else:
        config_path = Path(config_path)

    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(exclude_none=True, mode="json")

    # Convert enum values to plain strings
    for provider in data.get("providers", []):
        if "type" in provider:
            provider["type"] = str(provider["type"])

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
