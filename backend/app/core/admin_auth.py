"""Administrative authorization.

Admin routes are protected with a bearer API key. The key is compared using a
constant-time comparison so timing differences cannot be used to recover it.
The key is never logged, echoed in errors, or included in responses.
"""

import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

# auto_error=False so we can return a consistent, safe error body.
_bearer = HTTPBearer(auto_error=False, description="Administrative API key")


def verify_admin_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """FastAPI dependency that rejects requests without a valid admin key."""
    if not settings.admin_key_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrative access is not configured on this deployment.",
        )
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrative authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # secrets.compare_digest avoids leaking the key through response timing.
    if not secrets.compare_digest(credentials.credentials, settings.ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The supplied administrative credentials are not valid.",
        )
    request.state.is_admin = True
