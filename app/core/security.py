import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLES = ("viewer", "operator", "admin")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(password, hashed_password)


def create_access_token(*, user_id: str, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )


def generate_api_key() -> str:
    """Return a new plaintext API key. Only shown once at issuance time."""
    return f"ipk_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """API keys are hashed with SHA-256 (not bcrypt) so they remain a fast,
    deterministic lookup key for the ``api_key_hash`` unique index."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
