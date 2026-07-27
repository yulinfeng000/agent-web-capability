from contextlib import asynccontextmanager
from importlib.resources import files
from typing import NoReturn

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .auth import Principal, TokenAuthenticator, verify_token
from .browser import BrowserPool
from .config import AppConfig, VALID_FETCH_FORMATS, VALID_SEARCH_FORMATS, load_config
from .errors import CapacityExceeded, InvalidInput, OperationTimeout, UpstreamFailure
from .mcp_server import create_mcp_http_app
from .search import SUPPORTED_ENGINES, get_engines_info, results_to_csv
from .service import WebCapabilityService


def get_service(request: Request) -> WebCapabilityService:
    return request.app.state.service


def _raise_http_error(exc: Exception) -> NoReturn:
    if isinstance(exc, InvalidInput):
        code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, CapacityExceeded):
        code = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(exc, OperationTimeout):
        code = status.HTTP_504_GATEWAY_TIMEOUT
    elif isinstance(exc, UpstreamFailure):
        code = status.HTTP_502_BAD_GATEWAY
    else:  # pragma: no cover
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
    raise HTTPException(status_code=code, detail=str(exc)) from exc


def create_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or load_config()
    pool = BrowserPool(app_config)
    service = WebCapabilityService(app_config, pool)
    authenticator = TokenAuthenticator(app_config.tokens)

    mcp_starlette_app = None
    mcp_http_app = None
    if app_config.mcp.enabled:
        _, mcp_starlette_app, mcp_http_app = create_mcp_http_app(
            app_config,
            service,
            authenticator,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if mcp_starlette_app is None:
            yield
            return
        async with mcp_starlette_app.router.lifespan_context(mcp_starlette_app):
            yield

    app = FastAPI(title="agent-web-capability", version="0.3.0", lifespan=lifespan)
    app.state.config = app_config
    app.state.browser_pool = pool
    app.state.service = service
    app.state.authenticator = authenticator

    static_path = files("agent_web_capability").joinpath("static")
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    @app.get("/")
    async def index():
        return FileResponse(str(static_path.joinpath("index.html")))

    @app.get("/fetch")
    async def fetch_url(
        url: str = Query(..., description="URL to fetch"),
        return_type: str = Query(
            app_config.fetch.default_return_type,
            description=f"Output format: {', '.join(sorted(VALID_FETCH_FORMATS))}",
        ),
        _principal: Principal = Depends(verify_token),
        capability_service: WebCapabilityService = Depends(get_service),
    ):
        try:
            content = await capability_service.fetch(url, return_type)
        except (InvalidInput, CapacityExceeded, OperationTimeout, UpstreamFailure) as exc:
            _raise_http_error(exc)
        return {
            "success": True,
            "url": url,
            "return_type": return_type,
            "content": content,
        }

    @app.get("/search")
    async def search(
        q: str = Query(..., description="Search query"),
        engine: str | None = Query(
            default=None,
            description=f"Search engine. Supported: {', '.join(sorted(SUPPORTED_ENGINES))}",
        ),
        num_results: int | None = Query(default=None, ge=1, le=50),
        format: str | None = Query(default=None, description="Response format: json or csv"),
        _principal: Principal = Depends(verify_token),
        capability_service: WebCapabilityService = Depends(get_service),
    ):
        engine_name = engine or app_config.search.default_engine
        count = num_results or app_config.search.default_num_results
        response_format = format or app_config.search.default_format
        if response_format not in VALID_SEARCH_FORMATS:
            _raise_http_error(
                InvalidInput(
                    f"Invalid format '{response_format}'. Must be one of: "
                    f"{', '.join(sorted(VALID_SEARCH_FORMATS))}"
                )
            )
        try:
            search_response = await capability_service.search(q, engine_name, count)
        except (InvalidInput, CapacityExceeded, OperationTimeout, UpstreamFailure) as exc:
            _raise_http_error(exc)

        if response_format == "csv":
            return Response(
                content=results_to_csv(search_response.results),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=search_results.csv"},
            )
        return {
            "success": True,
            "query": search_response.query,
            "engine": search_response.engine,
            "num_results": count,
            "format": response_format,
            "results": [result.model_dump() for result in search_response.results],
        }

    @app.get("/search/engines")
    async def search_engines():
        return {"success": True, "engines": get_engines_info()}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    if mcp_http_app is not None:
        app.mount("/", mcp_http_app, name="mcp")
    return app


app = create_app()
