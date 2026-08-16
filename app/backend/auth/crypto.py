"""auth/crypto.py — symmetric encryption for stored secrets (API keys).

Uses Fernet (AES-128-CBC + HMAC) from the `cryptography` package. The
encryption key is read from env var ENCRYPTION_KEY at first use. Generate one
with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Treat ENCRYPTION_KEY like a database password — losing it means every stored
API key in the api_keys table becomes unrecoverable, and every user must
re-add their keys.

In development if ENCRYPTION_KEY is unset, a deterministic key is derived
from JWT_SECRET so encrypt/decrypt still round-trips without crashing — but
this is NOT safe for production (anyone with the JWT_SECRET can decrypt the
api_keys table). Set ENCRYPTION_KEY explicitly in prod.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    key = os.getenv("ENCRYPTION_KEY")
    if key:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    else:
        # Dev-only fallback: derive a stable key from JWT_SECRET so existing
        # ciphertexts in the DB keep round-tripping when the server restarts.
        # NOT suitable for production — set ENCRYPTION_KEY explicitly.
        logger.warning(
            "ENCRYPTION_KEY env var not set — deriving key from JWT_SECRET "
            "for dev. Set ENCRYPTION_KEY explicitly before any production use."
        )
        secret = os.getenv("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION").encode()
        derived = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
        _fernet = Fernet(derived)
    return _fernet


def encrypt(plaintext: str) -> str:
    """Returns Fernet ciphertext as a urlsafe-base64 string."""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str:
    """Returns the plaintext or raises ValueError on tamper/wrong-key."""
    try:
        return _get_fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Failed to decrypt — ENCRYPTION_KEY changed or ciphertext is corrupt"
        ) from exc
