"""FastAPI dependency for automation API key authentication (n8n /pending-outreach endpoints).

The pending-outreach endpoints are called by external automation (n8n) that has no JWT.
They must be authenticated with a secret API key sent in the X-API-Key header.
This dependency looks up the owning user FROM the server-side key store, NOT from the request.

CRITICAL SECURITY:
- Never accept a user_id from the request. Always look up the user from the server-side
  key store. This prevents a client from claiming to be a different user.
- The API key is a shared secret between the app and the automation system (n8n).
  Store it securely in n8n and rotate regularly.
- The key_hash is stored in the database, not the plaintext key. Only the automation
  system knows the plaintext key.

Usage:

    @router.get("/pending-outreach")
    async def pending_outreach(user: dict = Depends(get_user_from_automation_api_key)):
        # Now you have the authenticated user. Filter by user["id"]
        analyses = await db_list_analyses(str(user["id"]))
        ...
"""

import hashlib
from fastapi import Depends, Header, HTTPException, status
from database import db_get_user_from_automation_key


async def get_user_from_automation_api_key(
    x_api_key: str | None = Header(default=None),
) -> dict:
    """Validate X-API-Key header and return the owning user. Raises 401 if invalid.
    
    The key is hashed with sha256 before lookup in the database to avoid storing
    plaintext secrets.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    # Hash the provided key before lookup
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()

    user = await db_get_user_from_automation_key(key_hash)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive automation API key",
        )

    return user
