import asyncio
from typing import cast
from urllib.parse import urlsplit

from .browser import BrowserPool, FetchCapacityError, FetchError, FetchTimeoutError
from .config import AppConfig, FetchFormat
from .errors import CapacityExceeded, InvalidInput, OperationTimeout, UpstreamFailure
from .models import SearchResponse
from .search import (
    SUPPORTED_ENGINES,
    SearchConfigurationError,
    SearchError,
    get_provider,
)


class WebCapabilityService:
    def __init__(self, config: AppConfig, browser_pool: BrowserPool) -> None:
        self.config = config
        self.browser_pool = browser_pool
        self.search_semaphore = asyncio.Semaphore(config.search.max_concurrent)

    async def fetch(self, url: str, return_type: str) -> str:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise InvalidInput("URL must be an absolute http:// or https:// URL")
        if return_type not in {"html", "markdown", "plain_text"}:
            raise InvalidInput(
                "Invalid return_type. Must be one of: html, markdown, plain_text"
            )

        try:
            return await self.browser_pool.fetch(url, cast(FetchFormat, return_type))
        except FetchCapacityError as exc:
            raise CapacityExceeded(str(exc)) from exc
        except FetchTimeoutError as exc:
            raise OperationTimeout(str(exc)) from exc
        except FetchError as exc:
            raise UpstreamFailure(str(exc)) from exc

    async def search(self, query: str, engine: str, num_results: int) -> SearchResponse:
        normalized_query = query.strip()
        normalized_engine = engine.lower()
        if not normalized_query:
            raise InvalidInput("Search query must not be empty")
        if normalized_engine not in SUPPORTED_ENGINES:
            supported = ", ".join(sorted(SUPPORTED_ENGINES))
            raise InvalidInput(f"Unknown search engine '{engine}'. Supported: {supported}")
        if num_results < 1 or num_results > 50:
            raise InvalidInput("num_results must be between 1 and 50")

        try:
            provider = get_provider(normalized_engine, self.config.search)
        except SearchConfigurationError as exc:
            raise InvalidInput(str(exc)) from exc

        try:
            await asyncio.wait_for(
                self.search_semaphore.acquire(),
                timeout=self.config.search.capacity_wait_timeout,
            )
        except TimeoutError as exc:
            raise CapacityExceeded(
                f"Server is at maximum search capacity ({self.config.search.max_concurrent})"
            ) from exc

        search_task = asyncio.create_task(provider.search(normalized_query, num_results))
        release_capacity = True
        try:
            results = await asyncio.wait_for(
                asyncio.shield(search_task), timeout=self.config.search.timeout
            )
        except TimeoutError as exc:
            release_capacity = False
            search_task.add_done_callback(self._release_search_capacity)
            raise OperationTimeout(
                f"Search timed out after {self.config.search.timeout:g}s"
            ) from exc
        except asyncio.CancelledError:
            release_capacity = False
            search_task.add_done_callback(self._release_search_capacity)
            raise
        except SearchError as exc:
            raise UpstreamFailure(str(exc)) from exc
        finally:
            if release_capacity:
                self.search_semaphore.release()

        return SearchResponse(
            query=normalized_query,
            engine=normalized_engine,
            results=results,
        )

    def _release_search_capacity(self, task: asyncio.Task) -> None:
        self.search_semaphore.release()
        if not task.cancelled():
            task.exception()
