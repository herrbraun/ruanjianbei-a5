from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.crud.user import create_admin, get_user_by_username  # noqa: E402
from app.database import SessionLocal  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        existing = get_user_by_username(db, "admin")
        if existing:
            print("Admin user already exists.")
            return

        create_admin(db, username="admin", password="123456", display_name="系统管理员")
        print("Admin user created: admin / 123456")
    finally:
        db.close()


if __name__ == "__main__":
    main()
