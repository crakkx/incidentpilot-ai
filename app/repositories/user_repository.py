from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_user_by_email(db: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return db.execute(statement).scalar_one_or_none()


def get_user_by_api_key_hash(db: Session, api_key_hash: str) -> User | None:
    statement = select(User).where(User.api_key_hash == api_key_hash)
    return db.execute(statement).scalar_one_or_none()


def get_user(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def create_user(
    db: Session,
    *,
    email: str,
    hashed_password: str,
    role: str,
    api_key_hash: str | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password=hashed_password,
        role=role,
        api_key_hash=api_key_hash,
    )

    db.add(user)
    db.flush()

    return user


def set_api_key_hash(db: Session, user: User, api_key_hash: str) -> User:
    user.api_key_hash = api_key_hash
    db.flush()
    return user


def list_all_users(db: Session) -> list[User]:
    statement = select(User).order_by(User.created_at.desc())
    return list(db.execute(statement).scalars().all())


def update_user_role(db: Session, user: User, role: str) -> User:
    user.role = role
    db.commit()
    db.refresh(user)
    return user


def update_user_status(db: Session, user: User, is_active: bool) -> User:
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()

