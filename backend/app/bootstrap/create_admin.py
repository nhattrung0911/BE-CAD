"""Seed an admin user from the CLI.

Usage:
    python -m app.bootstrap.create_admin --email a@b.com --password 'somepass'
    python -m app.bootstrap.create_admin --email a@b.com  # prompts for password
"""
from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.auth import ROLE_ADMIN, hash_password
from app.core.database import SessionLocal
from app.db.models import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote an admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", default=None, help="If omitted, prompted from stdin.")
    parser.add_argument("--role", default=ROLE_ADMIN, choices=["viewer", "uploader", "admin"])
    parser.add_argument("--promote-existing", action="store_true",
                        help="If user already exists, update role and password instead of failing.")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("ERROR: password must be at least 8 characters", file=sys.stderr)
        return 2

    email = args.email.strip().lower()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing and not args.promote_existing:
            print(f"ERROR: user {email} already exists. Use --promote-existing to update.", file=sys.stderr)
            return 3
        if existing:
            existing.role = args.role
            existing.password_hash = hash_password(password)
            existing.is_active = True
            db.commit()
            print(f"OK: updated {email} (role={args.role})")
            return 0
        user = User(email=email, password_hash=hash_password(password), role=args.role, is_active=True)
        db.add(user)
        db.commit()
        print(f"OK: created {email} (id={user.id}, role={args.role})")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
