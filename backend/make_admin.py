"""
Promotes a user to admin role, by email.

Usage:
    python make_admin.py test2@example.com
"""

import sys

from app.database import SessionLocal
from app.models import User, UserRole


def make_admin(email: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"No user found with email: {email}")
            return

        user.role = UserRole.admin
        db.commit()
        print(f"'{user.full_name}' ({user.email}) is now an admin.")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python make_admin.py <email>")
        sys.exit(1)

    make_admin(sys.argv[1])
