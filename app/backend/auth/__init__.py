"""auth package — signup/login/refresh/forgot-password + (disabled) Google OAuth.

Re-exports `router` so `main.py` keeps working with the existing line:

    import auth
    app.include_router(auth.router, prefix="/api/auth", ...)
"""

from .routes import router
from .deps import get_current_user, get_current_user_optional
from .utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    FRONTEND_URL,
    JWT_ALGORITHM,
    JWT_SECRET,
    REFRESH_COOKIE_NAME,
    REFRESH_TOKEN_EXPIRE_DAYS,
    clear_refresh_cookie,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    set_refresh_cookie,
    verify_password,
)

__all__ = [
    "router",
    "get_current_user",
    "get_current_user_optional",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
    "hash_token",
    "set_refresh_cookie",
    "clear_refresh_cookie",
    "REFRESH_COOKIE_NAME",
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    "FRONTEND_URL",
]
