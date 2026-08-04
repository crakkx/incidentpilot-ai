from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

import jwt

from app.core.security import decode_access_token, hash_api_key
from app.db.session import get_db
from app.models import User
from app.repositories.user_repository import get_user, get_user_by_api_key_hash

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
    api_key: str | None = Security(_api_key_scheme),
) -> User:
    """Authenticate via ``Authorization: Bearer <jwt>`` or ``X-API-Key``.

    Either path is accepted so browser clients can use short-lived JWTs while
    scripts/CI use a long-lived API key through the same dependency.
    """
    if api_key:
        user = get_user_by_api_key_hash(db, hash_api_key(api_key))
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return user

    if bearer:
        try:
            payload = decode_access_token(bearer.credentials)
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user = get_user(db, payload.get("sub", ""))
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user

    raise HTTPException(status_code=401, detail="Authentication required")


def require_role(*roles: str):
    """FastAPI dependency factory: 403s unless ``current_user.role`` is in ``roles``."""

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return current_user

    return _check
