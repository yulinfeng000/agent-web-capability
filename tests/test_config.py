import pytest
from pydantic import ValidationError

from agent_web_capability.config import AppConfig, FetchConfig, MCPConfig, load_config


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("server", {"port": 70000}),
        ("fetch", {"max_concurrent": 0}),
        ("fetch", {"default_return_type": "invalid"}),
        ("search", {"default_num_results": 51}),
        ("search", {"default_engine": "invalid"}),
    ],
)
def test_invalid_configuration_is_rejected(section, value):
    with pytest.raises(ValidationError):
        AppConfig.model_validate({section: value})


def test_unknown_configuration_key_is_rejected():
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"fetch": {"timeuot": 5}})


def test_wildcard_mcp_origin_is_rejected():
    with pytest.raises(ValidationError):
        MCPConfig(allowed_origins=["*"])


def test_environment_overrides_mcp_security(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text("mcp:\n  enabled: false\n", encoding="utf-8")
    monkeypatch.setenv("MCP_MOUNT", "1")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "api.example.com,localhost:*")
    monkeypatch.setenv("MCP_CORS_ORIGINS", "https://console.example.com")

    config = load_config(str(config_path))
    assert config.mcp.enabled is True
    assert config.mcp.allowed_hosts == ["api.example.com", "localhost:*"]
    assert config.mcp.allowed_origins == ["https://console.example.com"]
