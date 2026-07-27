import logging
import os
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from .auth import MCPAuthMiddleware, TokenAuthenticator
from .config import AppConfig
from .errors import CapabilityError
from .models import SearchResponse
from .service import WebCapabilityService

logger = logging.getLogger(__name__)


def _load_instructions() -> str:
    configured_path = os.environ.get("MCP_PROMPT_PATH")
    if configured_path:
        try:
            return Path(configured_path).read_text(encoding="utf-8")
        except OSError:
            logger.warning("MCP prompt file not found: %s", configured_path)

    return (
        files("agent_web_capability")
        .joinpath("mcp-prompt.md")
        .read_text(encoding="utf-8")
    )


def create_mcp_server(config: AppConfig, service: WebCapabilityService) -> FastMCP:
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=config.mcp.allowed_hosts,
        allowed_origins=config.mcp.allowed_origins,
    )
    mcp = FastMCP(
        name="agent-web-capability",
        instructions=_load_instructions(),
        json_response=True,
        stateless_http=True,
        streamable_http_path=config.mcp.path,
        transport_security=transport_security,
    )

    @mcp.tool(
        name="web_fetch",
        description="Fetch and render a web page with the Lightpanda browser.",
    )
    async def fetch_tool(
        url: str,
        return_type: Literal["html", "markdown", "plain_text"] = config.fetch.default_return_type,
    ) -> str:
        try:
            return await service.fetch(url, return_type)
        except CapabilityError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        name="web_search",
        description="Search the web and return structured title, URL, and snippet results.",
        structured_output=True,
    )
    async def search_tool(
        query: str,
        engine: Literal["duckduckgo", "tavily", "brave", "serpapi"] = config.search.default_engine,
        num_results: Annotated[int, Field(ge=1, le=50)] = config.search.default_num_results,
    ) -> SearchResponse:
        try:
            return await service.search(query, engine, num_results)
        except CapabilityError as exc:
            raise ToolError(str(exc)) from exc

    return mcp


def create_mcp_http_app(
    config: AppConfig,
    service: WebCapabilityService,
    authenticator: TokenAuthenticator,
) -> tuple[FastMCP, Starlette, ASGIApp]:
    mcp = create_mcp_server(config, service)
    starlette_app = mcp.streamable_http_app()
    wrapped: ASGIApp = MCPAuthMiddleware(starlette_app, authenticator)
    if config.mcp.allowed_origins:
        wrapped = CORSMiddleware(
            wrapped,
            allow_origins=config.mcp.allowed_origins,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Last-Event-ID",
                "Mcp-Protocol-Version",
                "Mcp-Session-Id",
            ],
            expose_headers=["Mcp-Session-Id"],
        )
    return mcp, starlette_app, wrapped
