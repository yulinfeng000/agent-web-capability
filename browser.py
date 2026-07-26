import asyncio
import logging

from config import AppConfig

logger = logging.getLogger(__name__)


class FetchError(Exception):
    pass


class FetchTimeoutError(FetchError):
    pass


class BrowserPool:
    def __init__(self, config: AppConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.fetch.max_concurrent)

    async def fetch(
        self,
        url: str,
        return_type: str,
    ) -> str:
        try:
            await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            raise FetchError(
                "Server is at maximum capacity. "
                f"Max concurrent requests: {self.config.fetch.max_concurrent}. "
                "Please try again later."
            )
        try:
            return await asyncio.wait_for(
                self._run_lightpanda(url, return_type),
                timeout=self.config.fetch.timeout,
            )
        except asyncio.TimeoutError:
            raise FetchTimeoutError(
                f"Request timed out after {self.config.fetch.timeout}s"
            )
        finally:
            self.semaphore.release()

    async def _run_lightpanda(self, url: str, return_type: str) -> str:
        bin_path = self.config.lightpanda.bin_path
        wait_ms = self.config.lightpanda.wait_ms

        dump_format = "markdown" if return_type == "plain_text" else return_type

        args = [
            bin_path,
            "fetch",
            "--dump",
            dump_format,
            "--wait-ms",
            str(wait_ms),
        ]

        if self.config.lightpanda.obey_robots:
            args.append("--obey-robots")

        args.append(url)

        logger.info(f"Spawning: {args}")

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise FetchError(
                f"Lightpanda binary not found at '{bin_path}'. "
                "Install it with: scripts/install_lightpanda.sh"
            )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.fetch.timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise

        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        if process.returncode != 0:
            logger.error(
                f"Lightpanda exited with code {process.returncode}: {stderr_text}"
            )
            raise FetchError(
                f"Lightpanda failed (exit code {process.returncode}): {stderr_text[:500]}"
            )

        content = stdout.decode("utf-8", errors="replace")

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
