import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


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


class TokenConfig(BaseModel):
    token: str
    name: str = ""


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    lightpanda: LightpandaConfig = LightpandaConfig()
    fetch: FetchConfig = FetchConfig()
    tokens: list[TokenConfig] = []


def load_config(config_path: Optional[str] = None) -> AppConfig:
    if config_path is None:
        config_path = os.environ.get("CONFIG_PATH", "config.yaml")

    data: dict = {}
    if Path(config_path).exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

    server = ServerConfig(**data.get("server", {}))
    lightpanda = LightpandaConfig(**data.get("lightpanda", {}))
    fetch = FetchConfig(**data.get("fetch", {}))

    tokens = [TokenConfig(**t) for t in data.get("tokens", [])]

    lightpanda.bin_path = os.environ.get("LIGHTPANDA_BIN", lightpanda.bin_path)
    fetch.timeout = int(os.environ.get("LIGHTPANDA_FETCH_TIMEOUT", fetch.timeout))
    fetch.max_concurrent = int(
        os.environ.get("LIGHTPANDA_MAX_CONCURRENT", fetch.max_concurrent)
    )

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
        tokens=tokens,
    )
