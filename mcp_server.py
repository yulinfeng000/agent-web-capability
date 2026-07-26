"""MCP server for lightpanda-webfetch.

Exposes the fetch functionality as MCP tools so the service can be called
by MCP clients (Claude Desktop, etc.) in addition to the REST API.
"""

import logging
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from browser import BrowserPool, FetchError, FetchTimeoutError
from config import AppConfig

logger = logging.getLogger(__name__)

VALID_RETURN_TYPES = {"html", "markdown", "plain_text"}


def _resolve_prompt_path() -> Path:
    """Resolve the MCP prompt file path relative to CWD."""
    prompt_path = os.environ.get("MCP_PROMPT_PATH", "mcp-prompt.md")
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
        name="lightpanda-webfetch",
        instructions=_load_instructions(),
    )

    @mcp.tool(
        name="fetch",
        description=(
            "Fetch and render a web page using the Lightpanda headless browser. "
            "Returns the page content in the specified format. "
            "Use this tool when you need to retrieve and read the content of a web page."
        ),
    )
    async def fetch_tool(
        url: str,
        return_type: str = "markdown",
    ) -> str:
        """Fetch a web page and return its rendered content.

        Args:
            url: The URL to fetch. Must start with http:// or https://.
            return_type: Output format. One of: html, markdown, plain_text.
                         Default is markdown (best for LLM consumption).
        """
        if not url.startswith(("http://", "https://")):
            return (
                f"Error: URL must start with http:// or https://. Got: {url}"
            )

        if return_type not in VALID_RETURN_TYPES:
            return (
                f"Error: Invalid return_type '{return_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_RETURN_TYPES))}"
            )

        try:
            content = await pool.fetch(url, return_type)
            return content
        except FetchTimeoutError as e:
            return f"Error: Request timed out - {e}"
        except FetchError as e:
            return f"Error: Fetch failed - {e}"

    return mcp
