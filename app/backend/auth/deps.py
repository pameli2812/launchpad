"""auth/deps.py — FastAPI dependencies: get_current_user (JWT) and
get_user_from_extension_token (long-lived opaque token, for the browser extension).
"""

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from .utils import decode_access_token
from .db import db_get_user_by_id, db_user_from_extension_token

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """Validate Bearer token and return the user row. Raises 401 if invalid."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload["sub"]
    except (JWTError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = await db_get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict | None:
    """Like get_current_user but returns None instead of raising."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


# ── Extension token auth (separate from JWT) ──────────────────────────────────
# The browser extension can't easily ride along on the SPA's auth cookies
# (different origin). It sends X-Launchpad-Extension-Token instead — a
# long-lived opaque token the user generates in Settings and pastes in once.

async def get_user_from_extension_token(
    x_launchpad_extension_token: str | None = Header(default=None),
) -> dict:
    if not x_launchpad_extension_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Launchpad-Extension-Token header",
        )
    user = await db_user_from_extension_token(x_launchpad_extension_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked extension token",
        )
    return user
