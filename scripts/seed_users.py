"""Create the demo viewer/operator/admin accounts from env vars.

Reads SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD (and the operator/viewer
equivalents) from settings. Any role whose email/password isn't set is
skipped. Safe to re-run — existing users are left untouched.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.repositories.user_repository import (  # noqa: E402
    create_user,
    get_user_by_email,
)

SEED_ACCOUNTS = [
    ("viewer", "seed_viewer_email", "seed_viewer_password"),
    ("operator", "seed_operator_email", "seed_operator_password"),
    ("admin", "seed_admin_email", "seed_admin_password"),
]


def main() -> None:
    db = SessionLocal()

    try:
        for role, email_attr, password_attr in SEED_ACCOUNTS:
            email = getattr(settings, email_attr)
            password = getattr(settings, password_attr)

            if not email or not password:
                print(f"skip {role}: {email_attr}/{password_attr} not set")
                continue

            if get_user_by_email(db, email):
                print(f"skip {role}: {email} already exists")
                continue

            create_user(
                db,
                email=email,
                hashed_password=hash_password(password),
                role=role,
            )
            db.commit()
            print(f"created {role}: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
