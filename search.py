"""Search provider abstraction for agent-web-capability.

Provides a unified interface over multiple search backends:
- DuckDuckGo (free, no API key) via ddgs
- Tavily (API key required) via tavily-python
- Brave Search (API key required) via brave-search-python-client
- SerpAPI (API key required) via serpapi
"""

import asyncio
import csv
import io
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from config import SearchConfig

logger = logging.getLogger(__name__)

SUPPORTED_ENGINES = frozenset({"duckduckgo", "tavily", "brave", "serpapi"})


@dataclass
class SearchResult:
    """A single search result from any provider."""

    title: str
    url: str
    snippet: str


class SearchError(Exception):
    """Raised when a search provider fails."""


class SearchProvider(ABC):
    """Abstract base for search providers."""

    def __init__(self, config: SearchConfig):
        self.config = config

    @abstractmethod
    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        """Execute a search query and return results."""
        ...


class DuckDuckGoProvider(SearchProvider):
    """Free DuckDuckGo search via ddgs (HTML scraping). No API key required."""

    def __init__(self, config: SearchConfig):
        super().__init__(config)

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        try:
            from ddgs import DDGS
        except ImportError:
            raise SearchError(
                "ddgs package is required for DuckDuckGo search. "
                "Install with: pip install ddgs"
            )

        def _sync_search():
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=num_results))
            return raw

        try:
            raw_results = await asyncio.to_thread(_sync_search)
        except Exception as e:
            raise SearchError(f"DuckDuckGo search failed: {e}")

        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
            )
            for r in raw_results
        ]


class TavilyProvider(SearchProvider):
    """Tavily search API. Requires tavily_api_key in config."""

    def __init__(self, config: SearchConfig):
        super().__init__(config)
        if not config.tavily_api_key:
            raise SearchError(
                "Tavily API key is required. Set tavily_api_key in config or TAVILY_API_KEY env var."
            )

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        try:
            from tavily import TavilyClient
        except ImportError:
            raise SearchError(
                "tavily-python package is required for Tavily search. "
                "Install with: pip install agent-web-capability[tavily]"
            )

        def _sync_search():
            client = TavilyClient(api_key=self.config.tavily_api_key)
            return client.search(query, max_results=num_results)

        try:
            response = await asyncio.to_thread(_sync_search)
        except Exception as e:
            raise SearchError(f"Tavily search failed: {e}")

        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
            )
            for r in response.get("results", [])
        ]


class BraveProvider(SearchProvider):
    """Brave Search API. Requires brave_api_key in config."""

    def __init__(self, config: SearchConfig):
        super().__init__(config)
        if not config.brave_api_key:
            raise SearchError(
                "Brave API key is required. Set brave_api_key in config or BRAVE_API_KEY env var."
            )

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        try:
            from brave_search_python_client import BraveSearch, WebSearchRequest
        except ImportError:
            raise SearchError(
                "brave-search-python-client package is required for Brave search. "
                "Install with: pip install agent-web-capability[brave]"
            )

        client = BraveSearch(api_key=self.config.brave_api_key)
        request = WebSearchRequest(q=query, count=num_results)

        try:
            response = await client.web(request)
        except Exception as e:
            raise SearchError(f"Brave search failed: {e}")

        # Brave returns different response shapes; handle both
        web = getattr(response, "web", None)
        results_list = getattr(web, "results", None) if web else getattr(response, "results", [])

        return [
            SearchResult(
                title=getattr(r, "title", ""),
                url=getattr(r, "url", ""),
                snippet=getattr(r, "description", ""),
            )
            for r in (results_list or [])
        ]


class SerpAPIProvider(SearchProvider):
    """SerpAPI search. Requires serpapi_api_key in config. Uses Google by default."""

    def __init__(self, config: SearchConfig):
        super().__init__(config)
        if not config.serpapi_api_key:
            raise SearchError(
                "SerpAPI API key is required. Set serpapi_api_key in config or SERPAPI_API_KEY env var."
            )

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        try:
            import serpapi
        except ImportError:
            raise SearchError(
                "serpapi package is required for SerpAPI search. "
                "Install with: pip install agent-web-capability[serpapi]"
            )

        def _sync_search():
            client = serpapi.Client(api_key=self.config.serpapi_api_key)
            return client.search({
                "q": query,
                "engine": "google",
                "num": str(num_results),
            })

        try:
            response = await asyncio.to_thread(_sync_search)
        except Exception as e:
            raise SearchError(f"SerpAPI search failed: {e}")

        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=r.get("snippet", ""),
            )
            for r in response.get("organic_results", [])
        ]


# Provider registry
_PROVIDER_CLASSES: dict[str, type[SearchProvider]] = {
    "duckduckgo": DuckDuckGoProvider,
    "tavily": TavilyProvider,
    "brave": BraveProvider,
    "serpapi": SerpAPIProvider,
}


def get_provider(engine: str, config: SearchConfig) -> SearchProvider:
    """Create a search provider instance for the given engine."""
    engine = engine.lower()
    if engine not in _PROVIDER_CLASSES:
        raise SearchError(
            f"Unknown search engine '{engine}'. "
            f"Supported engines: {', '.join(sorted(_PROVIDER_CLASSES))}"
        )
    provider_class = _PROVIDER_CLASSES[engine]
    return provider_class(config)


def results_to_json(results: list[SearchResult], query: str, engine: str) -> str:
    """Serialize search results to a JSON string."""
    return json.dumps(
        {
            "query": query,
            "engine": engine,
            "results": [asdict(r) for r in results],
        },
        ensure_ascii=False,
        indent=2,
    )


def get_engines_info() -> list[dict[str, Any]]:
    """Return metadata for all supported search engines."""
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
            "description": "AI-optimized search API. Requires tavily_api_key in config.",
        },
        {
            "engine": "brave",
            "name": "Brave Search",
            "requires_api_key": True,
            "description": "Privacy-first independent search index. Requires brave_api_key in config.",
        },
        {
            "engine": "serpapi",
            "name": "SerpAPI",
            "requires_api_key": True,
            "description": "Multi-engine search API (Google, Bing, etc.). Requires serpapi_api_key in config.",
        },
    ]


def results_to_csv(results: list[SearchResult]) -> str:
    """Serialize search results to a CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["title", "url", "snippet"])
    for r in results:
        writer.writerow([r.title, r.url, r.snippet])
    return output.getvalue()
