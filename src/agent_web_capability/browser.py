import asyncio
import json
import logging
from urllib.parse import urlsplit

from .config import AppConfig, FetchFormat

logger = logging.getLogger(__name__)


class FetchError(Exception):
    pass


class FetchCapacityError(FetchError):
    pass


class FetchTimeoutError(FetchError):
    pass


class BrowserPool:
    def __init__(self, config: AppConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.fetch.max_concurrent)

    async def fetch(self, url: str, return_type: FetchFormat) -> str:
        try:
            await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=self.config.fetch.capacity_wait_timeout,
            )
        except TimeoutError as exc:
            raise FetchCapacityError(
                f"Server is at maximum fetch capacity ({self.config.fetch.max_concurrent})"
            ) from exc

        try:
            return await asyncio.wait_for(
                self._run_lightpanda(url, return_type),
                timeout=self.config.fetch.timeout,
            )
        except TimeoutError as exc:
            raise FetchTimeoutError(
                f"Request timed out after {self.config.fetch.timeout:g}s"
            ) from exc
        finally:
            self.semaphore.release()

    async def _run_lightpanda(self, url: str, return_type: FetchFormat) -> str:
        config = self.config
        dump_format = "markdown" if return_type == "plain_text" else return_type
        args = [
            config.lightpanda.bin_path,
            "fetch",
            "--json",
            "--dump",
            dump_format,
            "--wait-ms",
            str(config.lightpanda.wait_ms),
            "--terminate-ms",
            str(int(config.fetch.timeout * 1000)),
            "--http-max-response-size",
            str(config.fetch.max_response_size),
            "--v8-max-heap-mb",
            str(config.fetch.v8_max_heap_mb),
        ]
        if config.fetch.block_private_networks:
            args.append("--block-private-networks")
        if config.lightpanda.obey_robots:
            args.append("--obey-robots")
        args.append(url)

        logger.info("Fetching host %s with Lightpanda", urlsplit(url).hostname or "<invalid>")
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise FetchError(
                f"Lightpanda binary not found at '{config.lightpanda.bin_path}'"
            ) from exc

        try:
            stdout, _stderr = await process.communicate()
        except asyncio.CancelledError:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            raise

        if process.returncode != 0:
            logger.error("Lightpanda failed with exit code %s", process.returncode)
            raise FetchError(f"Lightpanda failed with exit code {process.returncode}")

        try:
            response = json.loads(stdout.decode("utf-8"))
            http_status = int(response.get("http_status", 0))
            content = response["content"]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.error("Lightpanda returned an invalid JSON response")
            raise FetchError("Lightpanda returned an invalid response") from exc
        if http_status == 0:
            raise FetchError("Navigation failed before receiving an HTTP response")
        if return_type == "plain_text":
            content = self._strip_markdown(content)
        return content

    @staticmethod
    def _strip_markdown(md: str) -> str:
        import re

        md = re.sub(r"^(#{1,6}\s+)", "", md, flags=re.MULTILINE)
        md = re.sub(r"\*\*(.+?)\*\*", r"\1", md)
        md = re.sub(r"\*(.+?)\*", r"\1", md)
        md = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
        md = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", md)
        md = re.sub(r"`{1,3}[^`]*`{1,3}", "", md)
        md = re.sub(r"^>\s+", "", md, flags=re.MULTILINE)
        md = re.sub(r"^[-*+]\s+", "", md, flags=re.MULTILINE)
        md = re.sub(r"^\d+\.\s+", "", md, flags=re.MULTILINE)
        md = re.sub(r"^(-{3,}|\*{3,})$", "", md, flags=re.MULTILINE)
        md = re.sub(r"\n{3,}", "\n\n", md)
        return md.strip()
