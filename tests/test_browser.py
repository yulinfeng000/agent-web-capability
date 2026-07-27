import asyncio

from agent_web_capability.browser import BrowserPool, FetchTimeoutError
from agent_web_capability.config import AppConfig, FetchConfig


class CompletedProcess:
    returncode = 0

    async def communicate(self):
        return b'{"url":"https://example.com","http_status":200,"content":"page"}', b""


def test_lightpanda_security_flags_are_enabled(monkeypatch):
    captured = []

    async def create_process(*args, **kwargs):
        captured.extend(args)
        return CompletedProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    config = AppConfig(fetch=FetchConfig(timeout=2, max_response_size=4096, v8_max_heap_mb=64))
    result = asyncio.run(BrowserPool(config).fetch("https://example.com", "markdown"))

    assert result == "page"
    assert "--json" in captured
    assert "--block-private-networks" in captured
    assert captured[captured.index("--http-max-response-size") + 1] == "4096"
    assert captured[captured.index("--terminate-ms") + 1] == "2000"
    assert captured[captured.index("--v8-max-heap-mb") + 1] == "64"


def test_timeout_kills_lightpanda_process(monkeypatch):
    class HangingProcess:
        returncode = None
        killed = False

        async def communicate(self):
            await asyncio.Event().wait()

        def kill(self):
            self.killed = True

        async def wait(self):
            self.returncode = -9

    process = HangingProcess()

    async def create_process(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    config = AppConfig(fetch=FetchConfig(timeout=0.01))

    async def run():
        try:
            await BrowserPool(config).fetch("https://example.com", "markdown")
        except FetchTimeoutError:
            return
        raise AssertionError("fetch did not time out")

    asyncio.run(run())
    assert process.killed is True
    assert process.returncode == -9
