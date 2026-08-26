"""One-off CLI to grant admin access. Not exposed via any API endpoint --
minting admins over HTTP is its own security surface, so this stays a
manually-run script.

Usage (from backend/): python -m scripts.promote_admin user@example.com
"""
import sys

from app.db.session import SessionLocal
from app.models import User


def promote(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            print(f"No user found with email {email!r}")
            sys.exit(1)
        if user.is_admin:
            print(f"{email} is already an admin")
            return
        user.is_admin = True
        db.commit()
        print(f"{email} is now an admin")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.promote_admin <email>")
        sys.exit(1)
    promote(sys.argv[1])
