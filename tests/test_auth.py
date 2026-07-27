import asyncio

import pytest
from fastapi.testclient import TestClient

from agent_web_capability.app import create_app
from agent_web_capability.auth import AuthenticationError, TokenAuthenticator
from agent_web_capability.config import AppConfig, TokenConfig


def test_anonymous_when_no_tokens_are_configured():
    principal = TokenAuthenticator([]).authenticate(None)
    assert principal.name == "anonymous"
    assert principal.authenticated is False


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_bearer_scheme_is_case_insensitive(scheme):
    authenticator = TokenAuthenticator([TokenConfig(token="secret", name="client")])
    principal = authenticator.authenticate(f"{scheme} secret")
    assert principal.name == "client"


@pytest.mark.parametrize("header", [None, "", "Basic secret", "Bearer", "Bearer wrong"])
def test_invalid_authorization_is_rejected(header):
    authenticator = TokenAuthenticator([TokenConfig(token="secret")])
    with pytest.raises(AuthenticationError):
        authenticator.authenticate(header)


def test_rest_authentication_uses_shared_authenticator():
    config = AppConfig(tokens=[TokenConfig(token="secret")])
    app = create_app(config)

    async def fake_fetch(url, return_type):
        return "content"

    app.state.service.fetch = fake_fetch
    client = TestClient(app)
    missing = client.get("/fetch", params={"url": "https://example.com"})
    accepted = client.get(
        "/fetch",
        params={"url": "https://example.com"},
        headers={"Authorization": "bearer secret"},
    )
    assert missing.status_code == 401
    assert accepted.status_code == 200
