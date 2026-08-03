"""FastAPI dependency that loads the current user's per-provider API keys
out of the api_keys table (Fernet-decrypted) and writes them into the
contextvar that the LLM provider chain reads from.

Use on any route that may call call_llm_json() down the stack:

    @router.post("/run")
    async def run_analysis(
        payload: RunAnalysisIn,
        user: dict = Depends(get_current_user),
        _keys: None = Depends(load_user_llm_keys),
    ): ...

The dep returns None — its job is the side effect of priming the contextvar
before the handler body runs. Decryption failures (e.g. ENCRYPTION_KEY was
rotated and an old key is in the DB) are swallowed; the affected provider
just falls back to env vars for that request.
"""

from __future__ import annotations

import logging

from fastapi import Depends

from auth import get_current_user_optional
from auth.crypto import decrypt
from database import db_get_decryptable_keys, db_get_active_provider
from launchpad.utils.openai_helper import set_user_keys

logger = logging.getLogger(__name__)


async def load_user_llm_keys(
    user: dict | None = Depends(get_current_user_optional),
) -> None:
    if not user:
        logger.debug("[LLM] No authenticated user; using server-level keys only")
        set_user_keys({})
        return

    user_id = str(user["id"])
    user_email = user.get("email", "unknown")
    
    logger.info(f"[LLM] Loading LLM keys for user: {user_email} ({user_id})")
    
    encrypted = await db_get_decryptable_keys(user_id)
    plaintext: dict[str, str] = {}
    for provider, ciphertext in encrypted.items():
        try:
            plaintext[provider] = decrypt(ciphertext)
            logger.debug(f"[LLM] ✓ Decrypted {provider} key for user {user_email}")
        except ValueError as exc:
            logger.warning(f"[LLM] ⚠ Failed to decrypt {provider} key for user {user_email}: {exc}")
    
    # Also determine which provider is active
    active = await db_get_active_provider(user_id)
    logger.info(f"[LLM] User {user_email}: Loaded keys: {list(plaintext.keys())} | Active: {active}")
    
    set_user_keys(plaintext)
