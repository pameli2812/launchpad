"""
auth/routes.py — signup, login, logout, refresh, forgot/reset password, Google OAuth.
All routes are under /api/auth (registered in main.py).
"""

from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, field_validator

from .utils import (
    FRONTEND_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
    REFRESH_COOKIE_NAME, clear_refresh_cookie, create_access_token,
    decode_access_token, hash_password, set_refresh_cookie, verify_password,
)
from .db import (
    db_consume_reset_token, db_create_refresh_token, db_create_reset_token,
    db_create_user, db_get_user_by_email, db_get_user_by_id,
    db_revoke_all_user_refresh_tokens, db_revoke_refresh_token,
    db_update_last_login, db_update_password, db_upsert_google_user,
    db_verify_refresh_token, db_verify_reset_token,
)

router = APIRouter()


# ── Request / response models ─────────────────────────────────────────────────

class SignUpIn(BaseModel):
    email: EmailStr
    full_name: str
    password: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("full_name")
    @classmethod
    def non_empty_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Full name is required")
        return v.strip()


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class DirectResetPasswordIn(BaseModel):
    """Local dev only: Reset password directly by email + new password."""
    email: EmailStr
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


def _user_response(user: dict) -> dict:
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "full_name": user["full_name"],
        "avatar_url": user.get("avatar_url"),
        "is_verified": user.get("is_verified", False),
    }


async def _issue_tokens(response: Response, user: dict) -> dict:
    """Create access + refresh tokens, set cookie, return response body."""
    user_id = str(user["id"])
    access_token = create_access_token(user_id, user["email"])
    raw_refresh = await db_create_refresh_token(user_id)
    set_refresh_cookie(response, raw_refresh)
    await db_update_last_login(user_id)
    return {"access_token": access_token, "token_type": "bearer", "user": _user_response(user)}


# ── Sign up ───────────────────────────────────────────────────────────────────

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: SignUpIn, response: Response):
    existing = await db_get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    user = await db_create_user(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        is_verified=True,   # skip email verification for now; add later if needed
    )
    return await _issue_tokens(response, user)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(payload: LoginIn, response: Response):
    user = await db_get_user_by_email(payload.email)
    if not user or not user.get("hashed_password"):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return await _issue_tokens(response, user)


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(
    response: Response,
    launchpad_refresh: Optional[str] = Cookie(default=None),
):
    if launchpad_refresh:
        await db_revoke_refresh_token(launchpad_refresh)
    clear_refresh_cookie(response)
    return {"message": "Logged out"}


# ── Token refresh ─────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh_token(
    response: Response,
    launchpad_refresh: Optional[str] = Cookie(default=None),
):
    if not launchpad_refresh:
        raise HTTPException(status_code=401, detail="No refresh token")
    user = await db_verify_refresh_token(launchpad_refresh)
    if not user:
        clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    # Rotate refresh token (revoke old, issue new)
    await db_revoke_refresh_token(launchpad_refresh)
    return await _issue_tokens(response, user)


# ── Forgot password ───────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordIn):
    """
    Forgot password endpoint.
    
    For local development: Returns the reset token directly so you can test password reset.
    In production: Would send email with reset link instead.
    """
    user = await db_get_user_by_email(payload.email)
    
    # Always return 200 — don't reveal whether the email exists (production security)
    if not user:
        return {
            "message": "If that email is registered you will receive a reset link shortly",
            "reset_token": None  # Local dev: null when email not found
        }

    raw_token = await db_create_reset_token(str(user["id"]))
    reset_url = f"{FRONTEND_URL}/reset-password?token={raw_token}"

    # ── For local development ────────────────────────────────────────────────
    # Return token directly in response for easy local testing
    print(f"\n[AUTH] Password reset link for {payload.email}:\n  {reset_url}\n")

    return {
        "message": "Password reset link generated. Use the reset_token below.",
        "reset_token": raw_token,  # ✅ Local dev: Return token directly
        "reset_url": reset_url     # ✅ Local dev: Also return full URL for convenience
    }


# ── Reset password ────────────────────────────────────────────────────────────

@router.post("/reset-password")
async def reset_password(payload: ResetPasswordIn, response: Response):
    user_id = await db_verify_reset_token(payload.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired")

    await db_update_password(user_id, hash_password(payload.new_password))
    await db_consume_reset_token(payload.token)
    # Revoke all existing refresh tokens so old sessions are invalidated
    await db_revoke_all_user_refresh_tokens(user_id)

    return {"message": "Password updated successfully. Please log in with your new password."}


# ── Direct password reset (local dev only) ──────────────────────────────────

@router.post("/reset-password-direct")
async def reset_password_direct(payload: DirectResetPasswordIn, response: Response):
    """
    ⚠️  LOCAL DEVELOPMENT ONLY — Direct password reset by email.
    
    In production, remove this endpoint or protect it with additional authentication.
    
    **Endpoint:** POST /api/auth/reset-password-direct
    
    **Request:**
    ```json
    {
      "email": "user@example.com",
      "new_password": "NewPassword123"
    }
    ```
    
    **Response:**
    ```json
    {
      "message": "Password updated successfully.",
      "user": {
        "id": "uuid",
        "email": "user@example.com",
        "full_name": "User Name",
        "avatar_url": null,
        "is_verified": false
      }
    }
    ```
    
    **Use case:** Local testing/debugging. Quickly reset a user's password without email flow.
    """
    user = await db_get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = str(user["id"])
    
    # Update password
    await db_update_password(user_id, hash_password(payload.new_password))
    
    # Revoke all existing refresh tokens so old sessions are invalidated
    await db_revoke_all_user_refresh_tokens(user_id)

    # Fetch updated user
    updated_user = await db_get_user_by_id(user_id)

    return {
        "message": "Password updated successfully.",
        "user": _user_response(updated_user)
    }


# ── Google OAuth — Step 1: redirect to Google (currently disabled) ────────────

@router.get("/google")
async def google_login():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "online",
        "prompt":        "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


# ── Google OAuth — Step 2: handle callback (currently disabled) ───────────────

@router.get("/google/callback")
async def google_callback(code: str, response: Response):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
        )
    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Google token exchange failed")

    tokens = token_resp.json()
    id_token = tokens.get("id_token")

    # NOTE: We decode the id_token without verifying its signature here for
    # simplicity. In production verify with google-auth.
    import base64
    import json as _json
    parts = id_token.split(".")
    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
    claims = _json.loads(base64.urlsafe_b64decode(padded))

    google_id  = claims["sub"]
    email      = claims.get("email", "")
    full_name  = claims.get("name", "")
    avatar_url = claims.get("picture")

    if not email:
        raise HTTPException(status_code=400, detail="Google did not return an email address")

    user = await db_upsert_google_user(email, full_name, google_id, avatar_url)

    access_token = create_access_token(str(user["id"]), user["email"])
    raw_refresh  = await db_create_refresh_token(str(user["id"]))
    await db_update_last_login(str(user["id"]))

    redir = RedirectResponse(f"{FRONTEND_URL}/?token={access_token}", status_code=302)
    set_refresh_cookie(redir, raw_refresh)
    return redir


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(request: Request):
    """Return the current user from the Bearer token in the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header[7:]
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db_get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return _user_response(user)
