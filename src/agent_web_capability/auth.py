import json
import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import TokenConfig


@dataclass(frozen=True)
class Principal:
    name: str
    authenticated: bool


class AuthenticationError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class TokenAuthenticator:
    def __init__(self, tokens: list[TokenConfig]) -> None:
        self._tokens = tuple(tokens)

    def authenticate(self, authorization: str | None) -> Principal:
        if not self._tokens:
            return Principal(name="anonymous", authenticated=False)

        if not authorization:
            raise AuthenticationError("Missing Authorization header. Use: Bearer <token>")

        scheme, separator, candidate = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not candidate:
            raise AuthenticationError("Missing Authorization header. Use: Bearer <token>")

        matched: TokenConfig | None = None
        for configured in self._tokens:
            if secrets.compare_digest(
                candidate.encode("utf-8"), configured.token.encode("utf-8")
            ):
                matched = configured

        if matched is None:
            raise AuthenticationError("Invalid API token")
        return Principal(name=matched.name or "token", authenticated=True)


security = HTTPBearer(auto_error=False)


def get_authenticator(request: Request) -> TokenAuthenticator:
    return request.app.state.authenticator


def verify_token(
    request: Request,
    _credentials=Depends(security),
    authenticator: TokenAuthenticator = Depends(get_authenticator),
) -> Principal:
    try:
        return authenticator.authenticate(request.headers.get("authorization"))
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


class MCPAuthMiddleware:
    def __init__(self, app: ASGIApp, authenticator: TokenAuthenticator) -> None:
        self.app = app
        self.authenticator = authenticator

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        authorization = None
        for header_name, header_value in scope.get("headers", []):
            if header_name.lower() == b"authorization":
                authorization = header_value.decode("latin-1")
                break

        try:
            self.authenticator.authenticate(authorization)
        except AuthenticationError as exc:
            await self._unauthorized(send, exc.detail)
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _unauthorized(send: Send, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
