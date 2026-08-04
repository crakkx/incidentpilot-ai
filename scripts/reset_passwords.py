import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.repositories.user_repository import get_user_by_email

def main():
    db = SessionLocal()
    try:
        users = [
            ("viewer", "seed_viewer_email", "seed_viewer_password"),
            ("operator", "seed_operator_email", "seed_operator_password"),
            ("admin", "seed_admin_email", "seed_admin_password"),
        ]
        
        for role, email_attr, pass_attr in users:
            email = getattr(settings, email_attr)
            new_password = getattr(settings, pass_attr)
            
            user = get_user_by_email(db, email)
            if user:
                user.hashed_password = hash_password(new_password)
                db.commit()
                print(f"Updated password for {email} to match your .env file.")
            else:
                print(f"User {email} not found. Run seed_users.py first.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
