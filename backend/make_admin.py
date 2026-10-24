"""Make a registered user an admin.

    python make_admin.py user@example.com

Register the user in the website first, then run this once.
Docker:  docker compose exec backend python /app/backend/make_admin.py user@example.com
"""
import sys

from sqlalchemy import func

from app.database import SessionLocal
from app.models import User, UserRole


def main():
    if len(sys.argv) != 2:
        print("Usage: python make_admin.py user@example.com")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if not user:
            print(f"No user with the email {email}. Register on the website first.")
            sys.exit(1)
        if user.role == UserRole.admin:
            print(f"{user.email} is already an admin.")
            return
        user.role = UserRole.admin
        db.commit()
        print(f"{user.email} is now an admin. Log out and log in again.")
    finally:
        db.close()


if __name__ == "__main__":
    main()