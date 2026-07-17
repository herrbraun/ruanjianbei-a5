from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import AdminProfile, LoginLog, User, VisitorProfile


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(select(User).where(User.id == user_id))


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.username) == username.strip().lower()))


def create_visitor(db: Session, username: str, password: str) -> User:
    normalized_username = username.strip()
    user = User(
        username=normalized_username,
        password_hash=get_password_hash(password),
        nickname=normalized_username,
        role="visitor",
    )
    db.add(user)
    db.flush()
    db.add(VisitorProfile(user_id=user.id, interest=None))
    db.commit()
    db.refresh(user)
    return user


def create_guest_visitor(
    db: Session,
    *,
    guest_key_hash: str,
    nickname: str,
    expires_at: datetime,
    last_seen_at: datetime,
) -> User:
    user = User(
        username=None,
        password_hash=None,
        nickname=nickname,
        role="visitor",
        is_guest=True,
        guest_key_hash=guest_key_hash,
        guest_expires_at=expires_at,
        last_seen_at=last_seen_at,
    )
    db.add(user)
    db.flush()
    db.add(VisitorProfile(user_id=user.id, interest=None))
    db.commit()
    db.refresh(user)
    return user


def get_guest_by_key_hash(db: Session, guest_key_hash: str) -> User | None:
    return db.scalar(
        select(User).where(
            User.role == "visitor",
            User.is_guest.is_(True),
            User.guest_key_hash == guest_key_hash,
        )
    )


def touch_guest(db: Session, user: User, *, expires_at: datetime, last_seen_at: datetime) -> User:
    user.guest_expires_at = expires_at
    user.last_seen_at = last_seen_at
    db.commit()
    db.refresh(user)
    return user


def update_visitor_profile(
    db: Session,
    user: User,
    *,
    nickname: str | None = None,
    interests: list[str] | None = None,
) -> User:
    if nickname is not None:
        user.nickname = nickname
    if interests is not None and user.visitor_profile:
        user.visitor_profile.interest = ",".join(interests)
    db.commit()
    db.refresh(user)
    return user


def update_password(db: Session, user: User, new_password: str) -> None:
    user.password_hash = get_password_hash(new_password)
    db.commit()


def update_avatar(db: Session, user: User, avatar_url: str) -> User:
    user.avatar_url = avatar_url
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
