import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

# ── Structural constants (not user-configurable) ───────────────────────

VALID_FETCH_FORMATS: frozenset[str] = frozenset({"html", "markdown", "plain_text"})
VALID_SEARCH_FORMATS: frozenset[str] = frozenset({"json", "csv"})

DEFAULT_CONFIG_PATH = "config.yaml"
DEFAULT_MCP_PROMPT_PATH = "mcp-prompt.md"

# ── Config models (field defaults ARE the source of truth) ─────────────


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class LightpandaConfig(BaseModel):
    bin_path: str = "lightpanda"
    wait_ms: int = 2000
    obey_robots: bool = False


class FetchConfig(BaseModel):
    timeout: int = 30
    max_concurrent: int = 5
    default_return_type: str = "markdown"


class SearchConfig(BaseModel):
    default_engine: str = "duckduckgo"
    default_format: str = "json"
    default_num_results: int = 5
    tavily_api_key: str = ""
    brave_api_key: str = ""
    serpapi_api_key: str = ""


class TokenConfig(BaseModel):
    token: str
    name: str = ""


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    lightpanda: LightpandaConfig = LightpandaConfig()
    fetch: FetchConfig = FetchConfig()
    search: SearchConfig = SearchConfig()
    tokens: list[TokenConfig] = []


def load_config(config_path: Optional[str] = None) -> AppConfig:
    if config_path is None:
        config_path = os.environ.get("CONFIG_PATH", DEFAULT_CONFIG_PATH)

    data: dict = {}
    if Path(config_path).exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

    server = ServerConfig(**data.get("server", {}))
    lightpanda = LightpandaConfig(**data.get("lightpanda", {}))
    fetch = FetchConfig(**data.get("fetch", {}))
    search = SearchConfig(**data.get("search", {}))

    tokens = [TokenConfig(**t) for t in data.get("tokens", [])]

    # ── Env var overrides ──────────────────────────────────────────

    lightpanda.bin_path = os.environ.get("LIGHTPANDA_BIN", lightpanda.bin_path)

    fetch.timeout = int(os.environ.get("LIGHTPANDA_FETCH_TIMEOUT", fetch.timeout))
    fetch.max_concurrent = int(
        os.environ.get("LIGHTPANDA_MAX_CONCURRENT", fetch.max_concurrent)
    )
    fetch.default_return_type = os.environ.get(
        "FETCH_DEFAULT_RETURN_TYPE", fetch.default_return_type
    )

    search.default_engine = os.environ.get("SEARCH_DEFAULT_ENGINE", search.default_engine)
    search.default_format = os.environ.get("SEARCH_DEFAULT_FORMAT", search.default_format)
    search.default_num_results = int(os.environ.get("SEARCH_DEFAULT_NUM_RESULTS", search.default_num_results))
    search.tavily_api_key = os.environ.get("TAVILY_API_KEY", search.tavily_api_key)
    search.brave_api_key = os.environ.get("BRAVE_API_KEY", search.brave_api_key)
    search.serpapi_api_key = os.environ.get("SERPAPI_API_KEY", search.serpapi_api_key)

    env_tokens = os.environ.get("LIGHTPANDA_TOKENS")
    if env_tokens:
        for t in env_tokens.split(","):
            t = t.strip()
            if t:
                tokens.append(TokenConfig(token=t, name="env"))

    return AppConfig(
        server=server,
        lightpanda=lightpanda,
        fetch=fetch,
        search=search,
        tokens=tokens,
    )
