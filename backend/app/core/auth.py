"""Optional API key authentication.

When PC_API_KEY is set, all /api/* endpoints require a Bearer token.
When empty (default), authentication is disabled for local development.
WebSocket and health endpoints are always public.
"""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


async def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Dependency that enforces API key auth when configured."""
    # Auth disabled — allow all
    if not settings.api_key:
        return

    # Skip auth for health check
    if request.url.path == "/api/health":
        return

    if not credentials or credentials.credentials != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
