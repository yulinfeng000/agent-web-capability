import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from auth import get_config, verify_token
from browser import BrowserPool, FetchError, FetchTimeoutError
from config import (
    AppConfig,
    VALID_FETCH_FORMATS,
    VALID_SEARCH_FORMATS,
    load_config,
)
from search import (
    SUPPORTED_ENGINES,
    SearchError,
    get_engines_info,
    get_provider,
    results_to_csv,
    results_to_json,
)

app_config = load_config()
browser_pool = BrowserPool(app_config)


def get_browser_pool(config: AppConfig = Depends(get_config)) -> BrowserPool:
    return browser_pool


# --- MCP integration (optional, enabled via MCP_MOUNT=1) ---

_mcp_mount_enabled = os.environ.get("MCP_MOUNT", "").lower() in ("1", "true", "yes")
_mcp_session_manager = None

if _mcp_mount_enabled:
    from mcp_server import create_mcp_server
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from mcp.server.fastmcp.server import StreamableHTTPASGIApp
    from starlette.middleware.cors import CORSMiddleware
    from auth import MCPAuthMiddleware

    _mcp = create_mcp_server(app_config, browser_pool)
    _mcp_session_manager = StreamableHTTPSessionManager(
        app=_mcp._mcp_server,
        event_store=_mcp._event_store,
        retry_interval=_mcp._retry_interval,
        json_response=True,  # Return JSON directly (no SSE required)
        stateless=True,  # Each request handled independently
        security_settings=_mcp.settings.transport_security,
    )
    _mcp_token_list = [t.token for t in app_config.tokens]

    _mcp_cors_origins = os.environ.get("MCP_CORS_ORIGINS", "*").split(",")
    _mcp_cors_methods = os.environ.get("MCP_CORS_METHODS", "GET,POST,DELETE,OPTIONS").split(",")
    _mcp_cors_headers = os.environ.get("MCP_CORS_HEADERS", "*").split(",")
    _mcp_cors_expose = os.environ.get("MCP_CORS_EXPOSE_HEADERS", "Mcp-Session-Id").split(",")

    _mcp_asgi_app = CORSMiddleware(
        MCPAuthMiddleware(
            StreamableHTTPASGIApp(_mcp_session_manager),
            tokens=_mcp_token_list,
        ),
        allow_origins=_mcp_cors_origins,
        allow_methods=_mcp_cors_methods,
        allow_headers=_mcp_cors_headers,
        expose_headers=_mcp_cors_expose,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _mcp_session_manager is not None:
        async with _mcp_session_manager.run():
            yield
    else:
        yield


app = FastAPI(title="agent-web-capability", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount MCP streamable HTTP handler at /mcp
if _mcp_mount_enabled:
    from starlette.routing import Route

    app.routes.append(
        Route("/mcp", endpoint=_mcp_asgi_app, methods=["GET", "POST", "DELETE", "OPTIONS"])
    )


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/fetch")
async def fetch_url(
    url: str = Query(..., description="URL to fetch"),
    return_type: str = Query(
        app_config.fetch.default_return_type,
        description=f"Output format: {', '.join(sorted(VALID_FETCH_FORMATS))}",
    ),
    _token: str = Depends(verify_token),
    pool: BrowserPool = Depends(get_browser_pool),
):
    if return_type not in VALID_FETCH_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid return_type '{return_type}'. Must be one of: {', '.join(sorted(VALID_FETCH_FORMATS))}",
        )

    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http:// or https://",
        )

    try:
        content = await pool.fetch(url, return_type)
    except FetchTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=str(e),
        )
    except FetchError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )

    return {
        "success": True,
        "url": url,
        "return_type": return_type,
        "content": content,
    }


@app.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    engine: str = Query(
        default=None,
        description=f"Search engine. Supported: {', '.join(sorted(SUPPORTED_ENGINES))}",
    ),
    num_results: int = Query(
        default=None,
        ge=1,
        le=50,
        description="Number of results (1-50)",
    ),
    format: str = Query(
        default=None,
        description="Response format: json or csv",
    ),
    _token: str = Depends(verify_token),
):
    search_config = app_config.search
    engine_name = engine or search_config.default_engine
    count = num_results or search_config.default_num_results
    fmt = format or search_config.default_format

    if fmt not in VALID_SEARCH_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format '{fmt}'. Must be one of: {', '.join(sorted(VALID_SEARCH_FORMATS))}",
        )

    if engine_name not in SUPPORTED_ENGINES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown engine '{engine_name}'. Supported: {', '.join(sorted(SUPPORTED_ENGINES))}",
        )

    try:
        provider = get_provider(engine_name, search_config)
    except SearchError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    try:
        results = await provider.search(q, count)
    except SearchError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )

    if fmt == "csv":
        from fastapi.responses import Response

        return Response(
            content=results_to_csv(results),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=search_results.csv"},
        )

    return {
        "success": True,
        "query": q,
        "engine": engine_name,
        "num_results": count,
        "format": fmt,
        "results": [
            {"title": r.title, "url": r.url, "snippet": r.snippet}
            for r in results
        ],
    }


@app.get("/search/engines")
async def search_engines():
    """Return the list of supported search engines with metadata."""
    return {
        "success": True,
        "engines": get_engines_info(),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


def main():
    import uvicorn

    uvicorn.run(
        "main:app",
        host=app_config.server.host,
        port=app_config.server.port,
    )


if __name__ == "__main__":
    main()
