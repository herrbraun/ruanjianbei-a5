from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import AdminProfile, LoginLog, User, VisitorProfile


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(select(User).where(User.id == user_id))


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def create_visitor(db: Session, nickname: str, interest: str | None) -> User:
    user = User(nickname=nickname, role="visitor")
    db.add(user)
    db.flush()
    db.add(VisitorProfile(user_id=user.id, interest=interest))
    db.commit()
    db.refresh(user)
    return user


def create_admin(db: Session, username: str, password: str, display_name: str) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        nickname=display_name,
        role="admin",
    )
    db.add(user)
    db.flush()
    db.add(AdminProfile(user_id=user.id, display_name=display_name))
    db.commit()
    db.refresh(user)
    return user


def add_login_log(db: Session, user: User, ip_address: str | None) -> None:
    db.add(LoginLog(user_id=user.id, role=user.role, ip_address=ip_address))
    db.commit()
