"""Password hashing, JWT helpers, and reversible Vinted credential storage."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from config import get_settings

_BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Hash a password with bcrypt (compatible with hashes produced by older passlib)."""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str | int, extra_claims: dict[str, Any] | None = None) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT; raises JWTError on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def get_sub_from_token(token: str) -> str:
    """Return the ``sub`` claim from a valid token."""
    payload = decode_token(token)
    sub = payload.get("sub")
    if sub is None or not isinstance(sub, str):
        raise JWTError("Token missing sub")
    return sub


def _fernet_for_app() -> Fernet:
    """Symmetric key derived from JWT secret (same across restarts for decrypt)."""
    settings = get_settings()
    digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def is_legacy_bcrypt_vinted(stored: str | None) -> bool:
    """True if ``stored`` is an old bcrypt hash (not usable for Vinted login)."""
    return bool(stored and stored.startswith("$2"))


def encrypt_vinted_credential(plain: str) -> str:
    """Encrypt Vinted password for DB storage (automation needs plaintext at publish time)."""
    return _fernet_for_app().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_vinted_credential(stored: str | None) -> str | None:
    """Decrypt stored Vinted password; None if missing, legacy bcrypt, or invalid token."""
    if not stored or is_legacy_bcrypt_vinted(stored):
        return None
    try:
        return _fernet_for_app().decrypt(stored.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        return None


def store_user_vinted_password(plain: str | None) -> str | None:
    """Normalize and encrypt Vinted password for the user row; None clears the field."""
    if plain is None:
        return None
    stripped = plain.strip()
    return encrypt_vinted_credential(stripped) if stripped else None
