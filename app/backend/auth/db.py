"""auth/db.py — DB helpers for users, refresh tokens, reset tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from database import get_conn
from .utils import (
    generate_opaque_token, hash_token,
    REFRESH_TOKEN_EXPIRE_DAYS,
)


# ── Users ─────────────────────────────────────────────────────────────────────

async def db_create_user(
    email: str,
    full_name: str,
    hashed_password: Optional[str] = None,
    google_id: Optional[str] = None,
    avatar_url: Optional[str] = None,
    is_verified: bool = False,
) -> dict:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            INSERT INTO users (email, full_name, hashed_password, google_id, avatar_url, is_verified)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (email, full_name, hashed_password, google_id, avatar_url, is_verified),
        )
        return dict(await cur.fetchone())


async def db_get_user_by_email(email: str) -> Optional[dict]:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM users WHERE email = %s AND is_active = TRUE", (email,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_get_user_by_id(user_id: str) -> Optional[dict]:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM users WHERE id = %s::uuid AND is_active = TRUE", (user_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_get_user_by_google_id(google_id: str) -> Optional[dict]:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM users WHERE google_id = %s AND is_active = TRUE", (google_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_update_last_login(user_id: str) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE users SET last_login_at = now() WHERE id = %s::uuid", (user_id,)
        )


async def db_update_password(user_id: str, hashed_password: str) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE users SET hashed_password = %s WHERE id = %s::uuid",
            (hashed_password, user_id),
        )


async def db_upsert_google_user(
    email: str, full_name: str, google_id: str, avatar_url: Optional[str]
) -> dict:
    """Create or update a user from Google OAuth. Returns the user row."""
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM users WHERE google_id = %s OR email = %s LIMIT 1",
            (google_id, email),
        )
        existing = await cur.fetchone()
        if existing:
            cur2 = await conn.execute(
                """
                UPDATE users
                   SET google_id = %s, avatar_url = COALESCE(%s, avatar_url),
                       full_name = COALESCE(NULLIF(%s,''), full_name),
                       is_verified = TRUE, last_login_at = now()
                 WHERE id = %s
                RETURNING *
                """,
                (google_id, avatar_url, full_name, existing["id"]),
            )
            return dict(await cur2.fetchone())
        else:
            cur3 = await conn.execute(
                """
                INSERT INTO users (email, full_name, google_id, avatar_url, is_verified)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING *
                """,
                (email, full_name, google_id, avatar_url),
            )
            return dict(await cur3.fetchone())


# ── Refresh tokens ────────────────────────────────────────────────────────────

async def db_create_refresh_token(user_id: str) -> str:
    """Creates a refresh token row and returns the raw token."""
    raw, hashed = generate_opaque_token()
    expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (%s::uuid, %s, %s)
            """,
            (user_id, hashed, expires),
        )
    return raw


async def db_verify_refresh_token(raw: str) -> Optional[dict]:
    """Returns the user row if the token is valid, else None."""
    hashed = hash_token(raw)
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT u.* FROM refresh_tokens rt
            JOIN users u ON u.id = rt.user_id
            WHERE rt.token_hash = %s
              AND rt.revoked = FALSE
              AND rt.expires_at > now()
              AND u.is_active = TRUE
            """,
            (hashed,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_revoke_refresh_token(raw: str) -> None:
    hashed = hash_token(raw)
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE refresh_tokens SET revoked = TRUE WHERE token_hash = %s", (hashed,)
        )


async def db_revoke_all_user_refresh_tokens(user_id: str) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = %s::uuid", (user_id,)
        )


# ── Password reset tokens ─────────────────────────────────────────────────────

async def db_create_reset_token(user_id: str) -> str:
    """Creates a reset token (1-hour expiry) and returns the raw token."""
    raw, hashed = generate_opaque_token()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE user_id = %s::uuid AND used = FALSE",
            (user_id,),
        )
        await conn.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
            VALUES (%s::uuid, %s, %s)
            """,
            (user_id, hashed, expires),
        )
    return raw


async def db_verify_reset_token(raw: str) -> Optional[str]:
    """Returns user_id string if valid, else None."""
    hashed = hash_token(raw)
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT user_id FROM password_reset_tokens
            WHERE token_hash = %s AND used = FALSE AND expires_at > now()
            """,
            (hashed,),
        )
        row = await cur.fetchone()
        return str(row["user_id"]) if row else None


async def db_consume_reset_token(raw: str) -> None:
    hashed = hash_token(raw)
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE token_hash = %s", (hashed,)
        )


# ── Extension tokens (long-lived, opaque, sent in X-Launchpad-Extension-Token) ──

async def db_create_extension_token(user_id: str, label: str = "Browser extension") -> tuple[str, dict]:
    """Returns (raw_token, row_metadata). The raw token is shown to the user
    exactly once; only its sha256 hash is stored."""
    raw, hashed = generate_opaque_token()
    last_4 = raw[-4:]
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            INSERT INTO extension_tokens (user_id, token_hash, label, last_4)
            VALUES (%s::uuid, %s, %s, %s)
            RETURNING id, label, last_4, last_used_at, revoked, created_at
            """,
            (user_id, hashed, label, last_4),
        )
        meta = dict(await cur.fetchone())
        # JSON-serialize timestamps + UUID
        meta["id"] = str(meta["id"])
        for k in ("last_used_at", "created_at"):
            if meta.get(k):
                meta[k] = meta[k].isoformat()
    return raw, meta


async def db_list_extension_tokens(user_id: str) -> list[dict]:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT id, label, last_4, last_used_at, revoked, created_at
              FROM extension_tokens
             WHERE user_id = %s::uuid
             ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = []
        for r in await cur.fetchall():
            d = dict(r)
            d["id"] = str(d["id"])
            for k in ("last_used_at", "created_at"):
                if d.get(k):
                    d[k] = d[k].isoformat()
            rows.append(d)
        return rows


async def db_revoke_extension_token(user_id: str, token_id: str) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            UPDATE extension_tokens
               SET revoked = TRUE
             WHERE id = %s::uuid AND user_id = %s::uuid
            """,
            (token_id, user_id),
        )
        return cur.rowcount > 0


async def db_user_from_extension_token(raw: str) -> dict | None:
    """Returns the user row for a valid, non-revoked extension token. Updates
    last_used_at as a side effect."""
    hashed = hash_token(raw)
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            UPDATE extension_tokens
               SET last_used_at = now()
             WHERE token_hash = %s AND revoked = FALSE
             RETURNING user_id
            """,
            (hashed,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        cur2 = await conn.execute(
            "SELECT * FROM users WHERE id = %s AND is_active = TRUE",
            (row["user_id"],),
        )
        u = await cur2.fetchone()
        return dict(u) if u else None
