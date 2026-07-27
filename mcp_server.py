"""MCP server for agent-web-capability.

Exposes the fetch and search functionality as MCP tools so the service can be called
by MCP clients (Claude Desktop, etc.) in addition to the REST API.
"""

import logging
import os
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

from browser import BrowserPool, FetchError, FetchTimeoutError
from config import (
    AppConfig,
    DEFAULT_MCP_PROMPT_PATH,
    VALID_FETCH_FORMATS,
)
from search import (
    SUPPORTED_ENGINES,
    SearchError,
    get_provider,
    results_to_json,
)

logger = logging.getLogger(__name__)


def _resolve_prompt_path() -> Path:
    """Resolve the MCP prompt file path relative to CWD."""
    prompt_path = os.environ.get("MCP_PROMPT_PATH", DEFAULT_MCP_PROMPT_PATH)
    return Path(prompt_path)


def _load_instructions() -> str:
    """Load MCP server instructions from the prompt file."""
    path = _resolve_prompt_path()
    if path.exists():
        logger.info(f"Loading MCP instructions from {path}")
        return path.read_text(encoding="utf-8")
    logger.warning(f"MCP prompt file not found: {path}")
    return "A web page fetching service powered by Lightpanda headless browser."


def create_mcp_server(config: AppConfig, pool: BrowserPool) -> FastMCP:
    """Create and configure the MCP server with fetch tools."""

    mcp = FastMCP(
        name="agent-web-capability",
        instructions=_load_instructions(),
    )

    @mcp.tool(
        name="web_fetch",
        description=(
            "Fetch and render a web page using the Lightpanda headless browser. "
            "Returns the page content in the specified format. "
            "Use this tool when you need to retrieve and read the content of a web page."
        ),
    )
    async def fetch_tool(
        url: str,
        return_type: str = config.fetch.default_return_type,
    ) -> str:
        """Fetch a web page and return its rendered content.

        Args:
            url: The URL to fetch. Must start with http:// or https://.
            return_type: Output format. One of: html, markdown, plain_text.
        """
        if not url.startswith(("http://", "https://")):
            return (
                f"Error: URL must start with http:// or https://. Got: {url}"
            )

        if return_type not in VALID_FETCH_FORMATS:
            return (
                f"Error: Invalid return_type '{return_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_FETCH_FORMATS))}"
            )

        try:
            content = await pool.fetch(url, return_type)
            return content
        except FetchTimeoutError as e:
            return f"Error: Request timed out - {e}"
        except FetchError as e:
            return f"Error: Fetch failed - {e}"

    @mcp.tool(
        name="web_search",
        description=(
            "Search the web using a configurable search engine. "
            "Returns results as a JSON string with title, url, and snippet for each result. "
            "Use this tool when you need to find current information from the web."
        ),
    )
    async def search_tool(
        query: str,
        engine: Literal["duckduckgo", "tavily", "brave", "serpapi"] = config.search.default_engine,  # type: ignore[assignment]
        num_results: int = config.search.default_num_results,
    ) -> str:
        """Search the web and return results.

        Args:
            query: The search query string.
            engine: Search engine to use. One of: duckduckgo, tavily, brave, serpapi.
            num_results: Maximum number of results to return (1-50).
        """
        engine_name = engine.lower()
        if engine_name not in SUPPORTED_ENGINES:
            return (
                f"Error: Unknown engine '{engine}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_ENGINES))}"
            )

        if num_results < 1 or num_results > 50:
            return "Error: num_results must be between 1 and 50."

        try:
            provider = get_provider(engine_name, config.search)
        except SearchError as e:
            return f"Error: {e}"

        try:
            results = await provider.search(query, num_results)
        except SearchError as e:
            return f"Error: Search failed - {e}"

        return results_to_json(results, query, engine_name)

    return mcp
