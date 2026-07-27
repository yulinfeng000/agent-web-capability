import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

FetchFormat = Literal["html", "markdown", "plain_text"]
SearchFormat = Literal["json", "csv"]
SearchEngine = Literal["duckduckgo", "tavily", "brave", "serpapi"]

VALID_FETCH_FORMATS: frozenset[str] = frozenset({"html", "markdown", "plain_text"})
VALID_SEARCH_FORMATS: frozenset[str] = frozenset({"json", "csv"})

DEFAULT_CONFIG_PATH = "config.yaml"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServerConfig(StrictModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8010, ge=1, le=65535)


class LightpandaConfig(StrictModel):
    bin_path: str = "lightpanda"
    wait_ms: int = Field(default=2000, ge=0)
    obey_robots: bool = False


class FetchConfig(StrictModel):
    timeout: float = Field(default=30, gt=0)
    capacity_wait_timeout: float = Field(default=5, gt=0)
    max_concurrent: int = Field(default=5, ge=1)
    default_return_type: FetchFormat = "markdown"
    block_private_networks: bool = True
    max_response_size: int = Field(default=10 * 1024 * 1024, ge=1024)
    v8_max_heap_mb: int = Field(default=256, ge=16)


class SearchConfig(StrictModel):
    default_engine: SearchEngine = "duckduckgo"
    default_format: SearchFormat = "json"
    default_num_results: int = Field(default=5, ge=1, le=50)
    timeout: float = Field(default=20, gt=0)
    capacity_wait_timeout: float = Field(default=5, gt=0)
    max_concurrent: int = Field(default=10, ge=1)
    tavily_api_key: str = ""
    brave_api_key: str = ""
    serpapi_api_key: str = ""


class MCPConfig(StrictModel):
    enabled: bool = False
    path: str = "/mcp"
    allowed_hosts: list[str] = Field(
        default_factory=lambda: [
            "localhost",
            "localhost:*",
            "127.0.0.1",
            "127.0.0.1:*",
            "[::1]",
            "[::1]:*",
        ]
    )
    allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("MCP path must start with '/'")
        if value != "/" and value.endswith("/"):
            return value.rstrip("/")
        return value

    @field_validator("allowed_origins")
    @classmethod
    def reject_wildcard_origins(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("MCP allowed_origins must list explicit origins; '*' is not allowed")
        return value


class TokenConfig(StrictModel):
    token: str = Field(min_length=1)
    name: str = ""


class AppConfig(StrictModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    lightpanda: LightpandaConfig = Field(default_factory=LightpandaConfig)
    fetch: FetchConfig = Field(default_factory=FetchConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    tokens: list[TokenConfig] = Field(default_factory=list)


def _set_nested(data: dict[str, Any], section: str, key: str, value: Any) -> None:
    current = data.setdefault(section, {})
    if not isinstance(current, dict):
        raise ValueError(f"Configuration section '{section}' must be a mapping")
    current[key] = value


def _csv_env(name: str) -> list[str] | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool_env(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Environment variable {name} must be a boolean")


def load_config(config_path: str | None = None) -> AppConfig:
    path = Path(config_path or os.environ.get("CONFIG_PATH", DEFAULT_CONFIG_PATH))
    data: dict[str, Any] = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("Configuration root must be a mapping")
        data = loaded

    env_overrides: tuple[tuple[str, str, str, type], ...] = (
        ("LIGHTPANDA_BIN", "lightpanda", "bin_path", str),
        ("LIGHTPANDA_FETCH_TIMEOUT", "fetch", "timeout", float),
        ("LIGHTPANDA_MAX_CONCURRENT", "fetch", "max_concurrent", int),
        ("FETCH_DEFAULT_RETURN_TYPE", "fetch", "default_return_type", str),
        ("SEARCH_DEFAULT_ENGINE", "search", "default_engine", str),
        ("SEARCH_DEFAULT_FORMAT", "search", "default_format", str),
        ("SEARCH_DEFAULT_NUM_RESULTS", "search", "default_num_results", int),
        ("SEARCH_TIMEOUT", "search", "timeout", float),
        ("SEARCH_MAX_CONCURRENT", "search", "max_concurrent", int),
        ("TAVILY_API_KEY", "search", "tavily_api_key", str),
        ("BRAVE_API_KEY", "search", "brave_api_key", str),
        ("SERPAPI_API_KEY", "search", "serpapi_api_key", str),
    )
    for env_name, section, key, converter in env_overrides:
        if env_name in os.environ:
            _set_nested(data, section, key, converter(os.environ[env_name]))

    mcp_enabled = _bool_env("MCP_MOUNT")
    if mcp_enabled is not None:
        _set_nested(data, "mcp", "enabled", mcp_enabled)
    for env_name, key in (
        ("MCP_ALLOWED_HOSTS", "allowed_hosts"),
        ("MCP_CORS_ORIGINS", "allowed_origins"),
    ):
        values = _csv_env(env_name)
        if values is not None:
            _set_nested(data, "mcp", key, values)

    env_tokens = _csv_env("LIGHTPANDA_TOKENS")
    if env_tokens:
        tokens = data.setdefault("tokens", [])
        if not isinstance(tokens, list):
            raise ValueError("Configuration field 'tokens' must be a list")
        tokens.extend({"token": token, "name": "env"} for token in env_tokens)

    return AppConfig.model_validate(data)
