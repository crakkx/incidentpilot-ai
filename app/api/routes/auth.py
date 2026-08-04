from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.security import (
    create_access_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models import User
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    set_api_key_hash,
)
from app.schemas.auth import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    LoginRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, payload.email)

    if user is None or not user.is_active or not verify_password(
        payload.password, user.hashed_password
    ):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(access_token=token, role=user.role)


@router.post("/api-keys", response_model=ApiKeyCreateResponse)
def issue_api_key(
    payload: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    """Issue an API key for a service account (script/CI caller), creating the
    account if it doesn't exist yet. The key is only ever returned here —
    only its SHA-256 hash is stored."""
    user = get_user_by_email(db, payload.email)
    if user is None:
        user = create_user(
            db,
            email=payload.email,
            hashed_password=hash_password(generate_api_key()),
            role=payload.role,
        )
    else:
        user.role = payload.role

    api_key = generate_api_key()
    set_api_key_hash(db, user, hash_api_key(api_key))
    db.commit()

    return ApiKeyCreateResponse(email=user.email, role=user.role, api_key=api_key)
