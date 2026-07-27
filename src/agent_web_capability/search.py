"""Search provider adapters."""

import asyncio
import csv
import io
import logging
from abc import ABC, abstractmethod
from typing import Any

from .config import SearchConfig
from .models import SearchResult

logger = logging.getLogger(__name__)

SUPPORTED_ENGINES = frozenset({"duckduckgo", "tavily", "brave", "serpapi"})


class SearchError(Exception):
    pass


class SearchConfigurationError(SearchError):
    pass


class SearchProvider(ABC):
    def __init__(self, config: SearchConfig):
        self.config = config

    @abstractmethod
    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        ...


class DuckDuckGoProvider(SearchProvider):
    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        try:
            from ddgs import DDGS
        except ImportError as exc:
            raise SearchConfigurationError("DuckDuckGo search dependency is not installed") from exc

        def sync_search():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=num_results))

        try:
            raw_results = await asyncio.to_thread(sync_search)
        except Exception as exc:
            logger.error("DuckDuckGo search failed (%s)", type(exc).__name__)
            raise SearchError("DuckDuckGo search failed") from exc

        return [
            SearchResult(
                title=result.get("title", ""),
                url=result.get("href", ""),
                snippet=result.get("body", ""),
            )
            for result in raw_results
        ]


class TavilyProvider(SearchProvider):
    def __init__(self, config: SearchConfig):
        super().__init__(config)
        if not config.tavily_api_key:
            raise SearchConfigurationError("Tavily API key is not configured")

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        try:
            from tavily import TavilyClient
        except ImportError as exc:
            raise SearchConfigurationError("Tavily search dependency is not installed") from exc

        def sync_search():
            client = TavilyClient(api_key=self.config.tavily_api_key)
            return client.search(query, max_results=num_results)

        try:
            response = await asyncio.to_thread(sync_search)
        except Exception as exc:
            logger.error("Tavily search failed (%s)", type(exc).__name__)
            raise SearchError("Tavily search failed") from exc

        return [
            SearchResult(
                title=result.get("title", ""),
                url=result.get("url", ""),
                snippet=result.get("content", ""),
            )
            for result in response.get("results", [])
        ]


class BraveProvider(SearchProvider):
    def __init__(self, config: SearchConfig):
        super().__init__(config)
        if not config.brave_api_key:
            raise SearchConfigurationError("Brave API key is not configured")

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        try:
            from brave_search_python_client import BraveSearch, WebSearchRequest
        except ImportError as exc:
            raise SearchConfigurationError("Brave search dependency is not installed") from exc

        client = BraveSearch(api_key=self.config.brave_api_key)
        request = WebSearchRequest(q=query, count=num_results)
        try:
            response = await client.web(request)
        except Exception as exc:
            logger.error("Brave search failed (%s)", type(exc).__name__)
            raise SearchError("Brave search failed") from exc

        web = getattr(response, "web", None)
        results_list = getattr(web, "results", None) if web else getattr(response, "results", [])
        return [
            SearchResult(
                title=getattr(result, "title", ""),
                url=getattr(result, "url", ""),
                snippet=getattr(result, "description", ""),
            )
            for result in (results_list or [])
        ]


class SerpAPIProvider(SearchProvider):
    def __init__(self, config: SearchConfig):
        super().__init__(config)
        if not config.serpapi_api_key:
            raise SearchConfigurationError("SerpAPI key is not configured")

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        try:
            import serpapi
        except ImportError as exc:
            raise SearchConfigurationError("SerpAPI search dependency is not installed") from exc

        def sync_search():
            client = serpapi.Client(api_key=self.config.serpapi_api_key)
            return client.search({"q": query, "engine": "google", "num": str(num_results)})

        try:
            response = await asyncio.to_thread(sync_search)
        except Exception as exc:
            logger.error("SerpAPI search failed (%s)", type(exc).__name__)
            raise SearchError("SerpAPI search failed") from exc

        return [
            SearchResult(
                title=result.get("title", ""),
                url=result.get("link", ""),
                snippet=result.get("snippet", ""),
            )
            for result in response.get("organic_results", [])
        ]


_PROVIDER_CLASSES: dict[str, type[SearchProvider]] = {
    "duckduckgo": DuckDuckGoProvider,
    "tavily": TavilyProvider,
    "brave": BraveProvider,
    "serpapi": SerpAPIProvider,
}


def get_provider(engine: str, config: SearchConfig) -> SearchProvider:
    provider_class = _PROVIDER_CLASSES.get(engine.lower())
    if provider_class is None:
        raise SearchConfigurationError(f"Unknown search engine '{engine}'")
    return provider_class(config)


def get_engines_info() -> list[dict[str, Any]]:
    return [
        {
            "engine": "duckduckgo",
            "name": "DuckDuckGo",
            "requires_api_key": False,
            "description": "Free web search via DuckDuckGo. No API key required.",
        },
        {
            "engine": "tavily",
            "name": "Tavily",
            "requires_api_key": True,
            "description": "AI-optimized search API. Requires a configured API key.",
        },
        {
            "engine": "brave",
            "name": "Brave Search",
            "requires_api_key": True,
            "description": "Privacy-first independent search index. Requires a configured API key.",
        },
        {
            "engine": "serpapi",
            "name": "SerpAPI",
            "requires_api_key": True,
            "description": "Google-backed search results. Requires a configured API key.",
        },
    ]


def results_to_csv(results: list[SearchResult]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["title", "url", "snippet"])
    for result in results:
        writer.writerow([result.title, result.url, result.snippet])
    return output.getvalue()
