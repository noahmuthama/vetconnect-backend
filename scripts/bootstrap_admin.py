import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

import auth
import database
import models


def main() -> None:
    email = input("Administrator email: ").strip().lower()
    full_name = input("Administrator full name: ").strip()
    password = getpass.getpass("Administrator password: ")
    confirmation = getpass.getpass("Confirm administrator password: ")

    if not email or not full_name:
        raise SystemExit("Email and full name are required.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if len(password) < 10 or not any(character.isalpha() for character in password) or not any(character.isdigit() for character in password):
        raise SystemExit("Password must contain at least 10 characters, including a letter and a number.")

    db = database.SessionLocal()
    try:
        existing = db.scalar(select(models.User).where(models.User.email == email))
        if existing is not None:
            if existing.role != models.UserRole.ADMIN:
                raise SystemExit("That email already belongs to a non-administrator account.")
            raise SystemExit("An administrator with that email already exists.")

        admin = models.User(
            email=email,
            full_name=full_name,
            hashed_password=auth.get_password_hash(password),
            role=models.UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Administrator created successfully: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
