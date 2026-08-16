"""Settings routes — per-user LLM API keys and browser-extension tokens.

All routes here require an authenticated user (JWT bearer). Mounted at
/api/settings in main.py.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from auth import get_current_user
from auth.crypto import encrypt
from auth.db import (
    db_create_extension_token,
    db_list_extension_tokens,
    db_revoke_extension_token,
)
from database import (
    db_delete_api_key, db_list_api_keys, db_upsert_api_key,
    db_list_automation_keys, db_upsert_automation_key, db_delete_automation_key,
    db_get_active_provider,
)

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_PROVIDERS = {"anthropic", "openai", "gemini"}

# ── Provider fallback chain & model options ───────────────────────────────────

FALLBACK_CHAIN = ["anthropic", "openai", "gemini"]

MODELS_BY_PROVIDER = {
    "anthropic": [
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
        "claude-opus-4-7",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1",
    ],
    "gemini": [
        "gemini-2.0-flash",
        "gemini-2.5-pro",
    ],
}


# ── API keys ──────────────────────────────────────────────────────────────────

class SetApiKeyIn(BaseModel):
    provider: str
    api_key: str
    model: str | None = None

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ALLOWED_PROVIDERS:
            raise ValueError(
                f"provider must be one of {sorted(ALLOWED_PROVIDERS)}"
            )
        return v

    @field_validator("model")
    @classmethod
    def _validate_model(cls, v: str | None, info) -> str | None:
        if v is None:
            return None
        v = v.strip()
        provider = info.data.get("provider", "").lower()
        if provider not in MODELS_BY_PROVIDER:
            return v  # Provider not yet validated, will fail above
        if v not in MODELS_BY_PROVIDER[provider]:
            valid_models = ", ".join(MODELS_BY_PROVIDER[provider])
            raise ValueError(
                f"model must be one of: {valid_models}"
            )
        return v

    @field_validator("api_key")
    @classmethod
    def _non_empty_key(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 8:
            raise ValueError("api_key looks too short")
        return v


@router.get("/api-keys")
async def list_api_keys(user: dict = Depends(get_current_user)):
    """List the user's configured API keys with active provider info.
    
    Returns all 3 providers, showing which has a key and which is active.
    """
    user_id = str(user["id"])
    user_email = user.get("email", "unknown")
    
    logger.info(f"[API] GET /api-keys request - User: {user_email} ({user_id})")
    
    rows = await db_list_api_keys(user_id)
    
    # Compute active provider
    active_provider = await db_get_active_provider(user_id)
    
    # Normalize datetimes and compute is_active per provider
    for r in rows:
        for k in ("created_at", "updated_at"):
            if r.get(k):
                r[k] = r[k].isoformat()
        r["id"] = str(r["id"]) if r.get("id") else None
        # has_key: True if user saved a key for this provider
        r["has_key"] = r.get("last_4") is not None
        
        # Compute is_active: True if this provider is the active one
        if active_provider == r["provider"] or (active_provider == f"server_{r['provider']}" and not r["has_key"]):
            r["is_active"] = True
        else:
            r["is_active"] = False
    
    response = {"api_keys": rows, "active_provider": active_provider}
    
    # Log response summary
    saved_providers = [r["provider"] for r in rows if r["has_key"]]
    logger.info(f"[API] ✓ GET /api-keys response - User: {user_email} | Saved keys: {saved_providers} | Active: {active_provider}")
    logger.debug(f"[API] GET /api-keys response body: {response}")
    
    return response


@router.put("/api-keys")
async def set_api_key(
    payload: SetApiKeyIn,
    user: dict = Depends(get_current_user),
):
    """Set or replace the user's API key for a provider. Encrypted at rest
    with Fernet before insert."""
    user_id = str(user["id"])
    user_email = user.get("email", "unknown")
    
    logger.info(f"[API] PUT /api-keys request - User: {user_email} | Provider: {payload.provider} | Model: {payload.model}")
    
    encrypted = encrypt(payload.api_key)
    last_4 = payload.api_key[-4:]
    row = await db_upsert_api_key(
        user_id=user_id,
        provider=payload.provider,
        encrypted=encrypted,
        last_4=last_4,
        model=payload.model,
    )
    for k in ("created_at", "updated_at"):
        if row.get(k):
            row[k] = row[k].isoformat()
    row["id"] = str(row["id"])
    
    response = {"api_key": row, "message": f"{payload.provider} key saved"}
    logger.info(f"[API] ✓ PUT /api-keys success - User: {user_email} | Provider: {payload.provider} | Key: ••••{last_4}")
    logger.debug(f"[API] PUT /api-keys response: {response}")
    
    return response


@router.delete("/api-keys/{provider}")
async def delete_api_key(
    provider: str,
    user: dict = Depends(get_current_user),
):
    user_id = str(user["id"])
    user_email = user.get("email", "unknown")
    provider = provider.strip().lower()
    
    logger.info(f"[API] DELETE /api-keys/{provider} request - User: {user_email}")
    
    if provider not in ALLOWED_PROVIDERS:
        logger.warning(f"[API] ⚠ DELETE /api-keys/{provider} invalid provider - User: {user_email}")
        raise HTTPException(status_code=400, detail="invalid provider")
    deleted = await db_delete_api_key(user_id, provider)
    if not deleted:
        logger.warning(f"[API] ⚠ DELETE /api-keys/{provider} no key found - User: {user_email}")
        raise HTTPException(status_code=404, detail="no key set for this provider")
    
    response = {"message": f"{provider} key deleted"}
    logger.info(f"[API] ✓ DELETE /api-keys/{provider} success - User: {user_email}")
    logger.debug(f"[API] DELETE response: {response}")
    
    return response


@router.get("/api-keys/models")
async def list_available_models():
    """Return available model options per provider."""
    return {"models": MODELS_BY_PROVIDER}


# ── Extension tokens ──────────────────────────────────────────────────────────

class CreateExtTokenIn(BaseModel):
    label: str = "Browser extension"

    @field_validator("label")
    @classmethod
    def _trim(cls, v: str) -> str:
        v = (v or "").strip() or "Browser extension"
        if len(v) > 80:
            raise ValueError("label too long (max 80 chars)")
        return v


@router.get("/extension-tokens")
async def list_extension_tokens(user: dict = Depends(get_current_user)):
    rows = await db_list_extension_tokens(str(user["id"]))
    return {"tokens": rows}


@router.post("/extension-tokens", status_code=status.HTTP_201_CREATED)
async def create_extension_token(
    payload: CreateExtTokenIn,
    user: dict = Depends(get_current_user),
):
    """Create a new extension token. The raw token is returned EXACTLY ONCE —
    the client must show it to the user immediately and tell them to copy it."""
    raw, meta = await db_create_extension_token(
        user_id=str(user["id"]),
        label=payload.label,
    )
    return {
        "token": raw,               # show this once, then forget
        "metadata": meta,
        "message": "Copy this token now — it will not be shown again.",
    }


@router.delete("/extension-tokens/{token_id}")
async def revoke_extension_token(
    token_id: str,
    user: dict = Depends(get_current_user),
):
    revoked = await db_revoke_extension_token(str(user["id"]), token_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="token not found")
    return {"message": "token revoked"}


# ── Automation API keys (for n8n /pending-outreach endpoints) ──────────────────

import hashlib
import secrets
import string

class CreateAutomationApiKeyIn(BaseModel):
    label: str = "n8n automation"

    @field_validator("label")
    @classmethod
    def _trim(cls, v: str) -> str:
        v = (v or "").strip() or "n8n automation"
        if len(v) > 100:
            raise ValueError("label too long (max 100 chars)")
        return v


@router.get("/automation-api-keys")
async def list_automation_api_keys(user: dict = Depends(get_current_user)):
    """List the user's automation API keys (without the key hash).
    
    Used for n8n /pending-outreach endpoints. Admin can view keys in DB if user loses one.
    """
    rows = await db_list_automation_keys(str(user["id"]))
    for r in rows:
        for k in ("created_at", "last_used_at"):
            if r.get(k):
                r[k] = r[k].isoformat()
        r["id"] = str(r["id"])
        r["user_id"] = str(r["user_id"])
    return {"automation_keys": rows}


@router.post("/automation-api-keys", status_code=status.HTTP_201_CREATED)
async def create_automation_api_key(
    payload: CreateAutomationApiKeyIn,
    user: dict = Depends(get_current_user),
):
    """Generate a new automation API key for n8n /pending-outreach endpoints.
    
    The raw key is returned EXACTLY ONCE. User must copy and store it securely.
    If lost, admin can retrieve the hash from DB and regenerate.
    
    Returns:
        {
            "key": "raw-plaintext-key-shown-only-once",
            "label": "n8n automation",
            "last_4": "abc5",
            "message": "Copy this key now — it will not be shown again."
        }
    """
    # Generate a secure random key (32 chars alphanumeric)
    alphabet = string.ascii_letters + string.digits
    raw_key = ''.join(secrets.choice(alphabet) for _ in range(32))
    
    # Hash it for storage
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    last_4 = raw_key[-4:]
    
    # Store in DB
    meta = await db_upsert_automation_key(
        user_id=str(user["id"]),
        key_hash=key_hash,
        label=payload.label,
    )
    
    # Return the raw key ONCE (client must save it)
    return {
        "key": raw_key,
        "label": meta.get("label"),
        "last_4": last_4,
        "message": "Copy this key now — it will not be shown again. Store it securely (e.g., n8n vault).",
    }


@router.delete("/automation-api-keys/{key_id}")
async def delete_automation_api_key(
    key_id: str,
    user: dict = Depends(get_current_user),
):
    """Revoke an automation API key.
    
    After deletion, the key will no longer authenticate requests to /pending-outreach.
    """
    deleted = await db_delete_automation_key(str(user["id"]), key_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="automation key not found")
    return {"message": "automation API key deleted"}
