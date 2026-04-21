"""Configuration schema definitions using Pydantic."""

from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    api_key: Optional[str] = None
    reload: bool = False  # Enable auto-reload on code changes


class LoggingConfig(BaseModel):
    level: str = "info"
    log_dir: Optional[str] = None  # 日志目录，每次启动生成 lccg-{timestamp}.log


class ProviderConfig(BaseModel):
    name: str
    type: ProviderType
    priority: int = 100  # Lower number = higher priority
    base_url: str
    api_key: Optional[str] = None
    auth_scheme: str = "x-api-key"  # "x-api-key" | "bearer"
    models: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: int = 600  # seconds
    enabled: bool = True  # False = excluded from routing fallback chain


class DegradationConfig(BaseModel):
    """Configuration for provider health degradation behavior."""

    failure_threshold: int = 3  # Consecutive failures before degradation
    recovery_seconds: float = 60.0  # Seconds to wait before entering half-open state
    half_open_interval: float = 30.0  # Seconds between half-open probe requests
    half_open_max_requests: int = 1  # Max probe requests allowed in half-open state


class RouterConfig(BaseModel):
    model_config = {"protected_namespaces": ()}

    default: Optional[str] = None
    model_map: dict[str, Union[str, list[str]]] = Field(default_factory=dict)
    fallback: Optional[str] = None  # Global fallback: "provider,model"
    degradation: DegradationConfig = Field(default_factory=DegradationConfig)


class GatewayConfig(BaseModel):
    """Root configuration for LCCG."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    providers: list[ProviderConfig] = Field(default_factory=list)
    router: RouterConfig = Field(default_factory=RouterConfig)
