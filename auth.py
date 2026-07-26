from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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
