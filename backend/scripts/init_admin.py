from __future__ import annotations

from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.crud.user import create_admin, get_user_by_username  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402


def read_initial_admin_credentials() -> tuple[str, str]:
    username = os.getenv("INITIAL_ADMIN_USERNAME", settings.initial_admin_username).strip()
    password = os.getenv("INITIAL_ADMIN_PASSWORD", settings.initial_admin_password)
    weak_passwords = {"123456", "password", "admin123456", "replace-with-a-strong-admin-password"}
    if not username:
        raise RuntimeError("INITIAL_ADMIN_USERNAME 不能为空")
    if len(password) < 12 or password.lower() in weak_passwords:
        raise RuntimeError("请通过 INITIAL_ADMIN_PASSWORD 配置至少 12 位的管理员初始密码")
    return username, password


def main() -> None:
    username, password = read_initial_admin_credentials()
    db = SessionLocal()
    try:
        existing = get_user_by_username(db, username)
        if existing:
            print("Admin user already exists.")
            return

        create_admin(db, username=username, password=password, display_name="系统管理员")
        print(f"Admin user created: {username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
