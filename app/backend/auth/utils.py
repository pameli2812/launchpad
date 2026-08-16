"""
auth/utils.py — JWT creation/verification, password hashing, token helpers.

Required env vars:
    JWT_SECRET                  — long random string (openssl rand -hex 32)
    JWT_ALGORITHM               — default HS256
    ACCESS_TOKEN_EXPIRE_MINUTES — default 15
    REFRESH_TOKEN_EXPIRE_DAYS   — default 7
    FRONTEND_URL                — e.g. http://localhost:5173

Optional (Google OAuth — currently DISABLED. Leave unset to keep Google signup off):
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    GOOGLE_REDIRECT_URI
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from jose import JWTError, jwt

# ── Config ────────────────────────────────────────────────────────────────────

JWT_SECRET    = os.getenv("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS   = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS",   "7"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# ── Google OAuth (disabled by default) ────────────────────────────────────────
# These default to None so the import always succeeds. The routes in auth/routes.py
# guard their Google flow with `if not GOOGLE_CLIENT_ID:` and 501-out when unset.
# To re-enable, populate all three env vars.

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI")

# ── Password ──────────────────────────────────────────────────────────────────
# Uses bcrypt directly — passlib has a broken bcrypt backend on Python 3.11+.
# bcrypt hard-limits at 72 bytes; we truncate explicitly so there's no silent
# data loss and no ValueError.

def hash_password(plain: str) -> str:
    truncated = plain.encode("utf-8")[:72]
    return _bcrypt.hashpw(truncated, _bcrypt.gensalt(rounds=12)).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    truncated = plain.encode("utf-8")[:72]
    return _bcrypt.checkpw(truncated, hashed.encode("utf-8"))

# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "email": email, "exp": expire, "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> dict:
    """Returns payload dict or raises JWTError."""
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload

# ── Opaque refresh / reset tokens ─────────────────────────────────────────────

def generate_opaque_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Store the hash; send the raw."""
    raw = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed

def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

# ── Cookie helpers ────────────────────────────────────────────────────────────

REFRESH_COOKIE_NAME = "launchpad_refresh"

def set_refresh_cookie(response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=os.getenv("ENV", "development") == "production",
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )

def clear_refresh_cookie(response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/auth")
