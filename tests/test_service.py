import asyncio

import pytest

from agent_web_capability.config import AppConfig, SearchConfig
from agent_web_capability.errors import CapacityExceeded, InvalidInput, OperationTimeout
from agent_web_capability.service import WebCapabilityService
from agent_web_capability.models import SearchResult


class FakePool:
    async def fetch(self, url, return_type):
        return "content"


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "javascript:alert(1)", "https:///missing-host", "not-a-url"],
)
def test_invalid_fetch_urls_are_rejected(url):
    service = WebCapabilityService(AppConfig(), FakePool())
    with pytest.raises(InvalidInput):
        asyncio.run(service.fetch(url, "markdown"))


def test_empty_search_query_is_rejected():
    service = WebCapabilityService(AppConfig(), FakePool())
    with pytest.raises(InvalidInput):
        asyncio.run(service.search("  ", "duckduckgo", 5))


def test_timed_out_search_keeps_capacity_until_provider_finishes(monkeypatch):
    finished = asyncio.Event()

    class SlowProvider:
        async def search(self, query, num_results):
            await finished.wait()
            return [SearchResult(title="done", url="https://example.com", snippet="")]

    monkeypatch.setattr(
        "agent_web_capability.service.get_provider", lambda engine, config: SlowProvider()
    )
    config = AppConfig(
        search=SearchConfig(timeout=0.01, capacity_wait_timeout=0.01, max_concurrent=1)
    )
    service = WebCapabilityService(config, FakePool())

    async def run():
        with pytest.raises(OperationTimeout):
            await service.search("first", "duckduckgo", 1)
        with pytest.raises(CapacityExceeded):
            await service.search("second", "duckduckgo", 1)
        finished.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert service.search_semaphore.locked() is False

    asyncio.run(run())
