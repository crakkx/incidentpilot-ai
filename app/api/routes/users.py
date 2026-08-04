from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models import User
from app.repositories.user_repository import (
    create_user,
    delete_user,
    get_user,
    get_user_by_email,
    list_all_users,
    update_user_role,
    update_user_status,
)
from app.schemas.user import (
    UserCreateRequest,
    UserReadResponse,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


def _to_user_read(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "has_api_key": bool(user.api_key_hash),
        "created_at": user.created_at,
    }


@router.get("", response_model=list[UserReadResponse])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    users = list_all_users(db)
    return [_to_user_read(u) for u in users]


@router.post("", response_model=UserReadResponse, status_code=status.HTTP_201_CREATED)
def create_new_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    existing = get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    user = create_user(
        db,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.commit()
    return _to_user_read(user)


@router.patch("/{user_id}/role", response_model=UserReadResponse)
def update_role(
    user_id: str,
    payload: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user = update_user_role(db, user, payload.role)
    return _to_user_read(user)


@router.patch("/{user_id}/status", response_model=UserReadResponse)
def update_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id == admin.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own admin account",
        )

    user = update_user_status(db, user, payload.is_active)
    return _to_user_read(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own admin account",
        )

    delete_user(db, user)
