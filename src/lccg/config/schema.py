"""Configuration schema definitions using Pydantic."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    api_key: Optional[str] = None


class LoggingConfig(BaseModel):
    level: str = "info"
    log_dir: Optional[str] = None  # 日志目录，每次启动生成 lccg-{timestamp}.log


class ProviderConfig(BaseModel):
    name: str
    type: ProviderType
    base_url: str
    api_key: Optional[str] = None
    auth_scheme: str = "x-api-key"  # "x-api-key" | "bearer"
    models: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: int = 600  # seconds


class RouterConfig(BaseModel):
    default: Optional[str] = None
    background: Optional[str] = None
    think: Optional[str] = None
    long_context: Optional[str] = None
    long_context_threshold: int = 60000
    web_search: Optional[str] = None
    image: Optional[str] = None
    fallback: Optional[str] = None  # Global fallback: "provider,model"


class GatewayConfig(BaseModel):
    """Root configuration for LCCG."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    providers: list[ProviderConfig] = Field(default_factory=list)
    router: RouterConfig = Field(default_factory=RouterConfig)
