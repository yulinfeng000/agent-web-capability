from fastapi.testclient import TestClient

from agent_web_capability.auth import TokenAuthenticator
from agent_web_capability.config import AppConfig, MCPConfig, TokenConfig
from agent_web_capability.errors import InvalidInput
from agent_web_capability.mcp_server import create_mcp_http_app
from agent_web_capability.models import SearchResponse, SearchResult


class FakeService:
    async def fetch(self, url, return_type):
        raise InvalidInput("blocked test URL")

    async def search(self, query, engine, num_results):
        return SearchResponse(
            query=query,
            engine=engine,
            results=[SearchResult(title="Result", url="https://example.com", snippet="Text")],
        )


def _request(client, body, token="secret"):
    return client.post(
        "/mcp",
        json=body,
        headers={
            "Accept": "application/json, text/event-stream",
            "Authorization": f"bearer {token}",
        },
    )


def test_mcp_auth_error_and_tool_protocol_results():
    config = AppConfig(
        mcp=MCPConfig(enabled=True, allowed_hosts=["testserver"]),
        tokens=[TokenConfig(token="secret")],
    )
    _, _, asgi_app = create_mcp_http_app(
        config,
        FakeService(),
        TokenAuthenticator(config.tokens),
    )

    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    with TestClient(asgi_app) as client:
        unauthorized = client.post(
            "/mcp",
            json=initialize,
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert unauthorized.status_code == 401
        assert _request(client, initialize).status_code == 200

        fetch_result = _request(
            client,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "web_fetch", "arguments": {"url": "file:///etc/passwd"}},
            },
        ).json()["result"]
        assert fetch_result["isError"] is True

        search_result = _request(
            client,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "web_search", "arguments": {"query": "test"}},
            },
        ).json()["result"]
        assert search_result["isError"] is False
        assert search_result["structuredContent"]["results"][0]["title"] == "Result"


def test_mcp_rejects_unknown_host():
    config = AppConfig(mcp=MCPConfig(allowed_hosts=["api.example.com"]))
    _, _, asgi_app = create_mcp_http_app(config, FakeService(), TokenAuthenticator([]))
    with TestClient(asgi_app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert response.status_code == 421
