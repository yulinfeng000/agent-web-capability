from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.types import ASGIApp, Receive, Scope, Send

from config import AppConfig

security = HTTPBearer(auto_error=False)


def get_config() -> AppConfig:
    from main import app_config

    return app_config


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    config: AppConfig = Depends(get_config),
) -> str:
    if not config.tokens:
        return "no-auth"

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    token_map = {t.token: t for t in config.tokens}
    if token not in token_map:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


class MCPAuthMiddleware:
    """ASGI middleware that validates Bearer tokens for the MCP endpoint.

    Mirrors the same auth logic as the REST API: if tokens are configured,
    requests must include a valid Authorization: Bearer <token> header.
    If no tokens are configured, all requests are allowed.
    """

    def __init__(self, app: ASGIApp, tokens: list[str]) -> None:
        self.app = app
        self._tokens = set(tokens)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip auth for OPTIONS (CORS preflight)
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # If no tokens configured, allow all
        if not self._tokens:
            await self.app(scope, receive, send)
            return

        # Extract Bearer token
        auth_header = None
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"authorization":
                auth_header = header_value.decode()
                break

        if auth_header is None or not auth_header.startswith("Bearer "):
            await self._unauthorized(send, "Missing Authorization header. Use: Bearer <token>")
            return

        token = auth_header[len("Bearer "):]
        if token not in self._tokens:
            await self._unauthorized(send, "Invalid API token")
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _unauthorized(send: Send, detail: str) -> None:
        import json

        body = json.dumps({"error": detail}).encode()
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b"Bearer"),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
