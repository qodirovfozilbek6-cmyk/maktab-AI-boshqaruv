
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import (
    BOOTSTRAP_ADMIN_FULL_NAME,
    BOOTSTRAP_ADMIN_PASSWORD,
    BOOTSTRAP_ADMIN_USERNAME,
)
from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def main():
    username = BOOTSTRAP_ADMIN_USERNAME.strip().lower()
    full_name = BOOTSTRAP_ADMIN_FULL_NAME.strip()

    password = BOOTSTRAP_ADMIN_PASSWORD or getpass.getpass(
        "Yangi administrator paroli: "
    )

    if len(password) < 12:
        print("XATO: Parol kamida 12 belgidan iborat bo'lishi kerak.")
        sys.exit(1)

    db = SessionLocal()

    try:
        existing = db.scalar(
            select(User).where(User.username == username)
        )

        if existing:
            print(
                f"'{username}' loginli foydalanuvchi allaqachon mavjud. "
                "Hech narsa o'zgartirilmadi."
            )
            return

        admin = User(
            username=username,
            full_name=full_name,
            password_hash=hash_password(password),
            role="admin",
            school_id=None,
            is_active=True,
        )

        db.add(admin)
        db.commit()

        print("Administrator muvaffaqiyatli yaratildi.")
        print(f"Login: {username}")
        print("Parol ekranga chiqarilmadi.")

    except SQLAlchemyError:
        db.rollback()
        print("Baza xatosi. Hech qanday o'zgarish tasdiqlanmadi.")
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
