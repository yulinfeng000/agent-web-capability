from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from auth import get_config, verify_token
from browser import BrowserPool, FetchError, FetchTimeoutError
from config import AppConfig, load_config

app_config = load_config()
browser_pool = BrowserPool(app_config)

VALID_RETURN_TYPES = {"html", "markdown", "plain_text"}


def get_browser_pool(config: AppConfig = Depends(get_config)) -> BrowserPool:
    return browser_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="lightpanda-webfetch", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/fetch")
async def fetch_url(
    url: str = Query(..., description="URL to fetch"),
    return_type: str = Query(
        "markdown",
        description="Output format: html, markdown, or plain_text",
    ),
    _token: str = Depends(verify_token),
    pool: BrowserPool = Depends(get_browser_pool),
):
    if return_type not in VALID_RETURN_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid return_type '{return_type}'. Must be one of: {', '.join(sorted(VALID_RETURN_TYPES))}",
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
