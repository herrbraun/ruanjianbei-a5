from __future__ import annotations

import secrets
import string
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token, verify_password
from app.crud.user import (
    add_login_log,
    create_guest_visitor,
    create_visitor,
    get_guest_by_key_hash,
    get_user_by_id,
    get_user_by_username,
    update_avatar,
    update_password,
    update_visitor_profile,
    touch_guest,
)
from app.database import get_db
from app.models.spot import SpotTag
from app.models.user import User
from app.schemas.auth import (
    AdminLoginRequest,
    AuthResponse,
    GuestAuthResponse,
    GuestSessionRequest,
    InterestOptionsResponse,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    UserInfo,
    UsernameAvailabilityResponse,
    VisitorLoginRequest,
    VisitorRegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)
avatar_directory = Path(__file__).resolve().parents[2] / "uploads" / "avatars"
avatar_directory.mkdir(parents=True, exist_ok=True)
username_suffix_alphabet = string.ascii_lowercase + string.digits
guest_recovery_days = 30
guest_creation_limit = 10
guest_creation_window_seconds = 60 * 60
guest_creation_attempts: dict[str, deque[float]] = defaultdict(deque)
guest_creation_lock = Lock()


def parse_interests(user: User) -> list[str]:
    interest = user.visitor_profile.interest if user.visitor_profile else None
    if not interest:
        return []
    return [item.strip() for item in interest.split(",") if item.strip()]


def build_user_info(user: User) -> UserInfo:
    interests = parse_interests(user)
    return UserInfo(
        id=user.id,
        role=user.role,
        username=user.username,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        interest=",".join(interests) or None,
        interests=interests,
        needs_interest_setup=user.role == "visitor" and not interests,
        is_guest=user.is_guest,
    )


def issue_auth_response(user: User) -> AuthResponse:
    token = create_access_token({"user_id": user.id, "role": user.role})
    return AuthResponse(access_token=token, token_type="bearer", user=build_user_info(user))


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def hash_guest_key(guest_key: str) -> str:
    return sha256(guest_key.encode("utf-8")).hexdigest()


def allow_guest_creation(ip_address: str | None) -> bool:
    key = ip_address or "unknown"
    now = monotonic()
    with guest_creation_lock:
        if len(guest_creation_attempts) >= 1024:
            stale_keys = [
                item_key
                for item_key, item_attempts in guest_creation_attempts.items()
                if not item_attempts or now - item_attempts[-1] >= guest_creation_window_seconds
            ]
            for stale_key in stale_keys:
                guest_creation_attempts.pop(stale_key, None)
        attempts = guest_creation_attempts[key]
        while attempts and now - attempts[0] >= guest_creation_window_seconds:
            attempts.popleft()
        if len(attempts) >= guest_creation_limit:
            return False
        attempts.append(now)
        return True


def guest_is_recoverable(user: User, now: datetime) -> bool:
    if user.guest_expires_at is None:
        return False
    expires_at = user.guest_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > now


def generate_username_suggestions(db: Session, username: str) -> list[str]:
    base = username.strip()[:29]
    suggestions: list[str] = []
    for _ in range(60):
        suffix = "".join(secrets.choice(username_suffix_alphabet) for _ in range(3))
        candidate = f"{base}{suffix}"
        if candidate not in suggestions and get_user_by_username(db, candidate) is None:
            suggestions.append(candidate)
        if len(suggestions) == 3:
            break
    return suggestions


def list_interest_options(db: Session) -> list[str]:
    return list(db.scalars(select(SpotTag.name).distinct().order_by(SpotTag.name)).all())


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = decode_access_token(credentials.credentials)
    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user_id = int(payload["user_id"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


def require_visitor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "visitor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Visitor role required")
    return current_user


@router.get("/username-availability", response_model=UsernameAvailabilityResponse, include_in_schema=False)
def username_availability(
    username: str = Query(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]{3,32}$"),
    db: Session = Depends(get_db),
) -> UsernameAvailabilityResponse:
    available = get_user_by_username(db, username) is None
    return UsernameAvailabilityResponse(
        available=available,
        suggestions=[] if available else generate_username_suggestions(db, username),
    )


@router.post("/guest-session", response_model=GuestAuthResponse)
def guest_session(
    payload: GuestSessionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> GuestAuthResponse:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=guest_recovery_days)
    if payload.guest_key:
        user = get_guest_by_key_hash(db, hash_guest_key(payload.guest_key))
        if user is not None and guest_is_recoverable(user, now):
            user = touch_guest(db, user, expires_at=expires_at, last_seen_at=now)
            auth = issue_auth_response(user)
            return GuestAuthResponse(**auth.model_dump(), guest_key=None)

    if not allow_guest_creation(get_client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="匿名游客创建过于频繁，请稍后再试",
            headers={"Retry-After": str(guest_creation_window_seconds)},
        )
    guest_key = secrets.token_urlsafe(32)
    user = create_guest_visitor(
        db,
        guest_key_hash=hash_guest_key(guest_key),
        nickname=f"匿名游客 {guest_key[-4:].upper()}",
        expires_at=expires_at,
        last_seen_at=now,
    )
    auth = issue_auth_response(user)
    return GuestAuthResponse(**auth.model_dump(), guest_key=guest_key)


@router.post("/visitor-register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def visitor_register(
    payload: VisitorRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthResponse:
    if get_user_by_username(db, payload.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "username_taken",
                "message": "账号名已被占用，请更改",
                "suggestions": generate_username_suggestions(db, payload.username),
            },
        )
    try:
        user = create_visitor(db, payload.username, payload.password)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "username_taken",
                "message": "账号名已被占用，请更改",
                "suggestions": generate_username_suggestions(db, payload.username),
            },
        ) from exc
    add_login_log(db, user=user, ip_address=get_client_ip(request))
    return issue_auth_response(user)


@router.post("/visitor-login", response_model=AuthResponse, include_in_schema=False)
def visitor_login(payload: VisitorLoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    user = get_user_by_username(db, payload.username)
    if user is None or user.role != "visitor" or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    add_login_log(db, user=user, ip_address=get_client_ip(request))
    return issue_auth_response(user)


@router.post("/admin-login", response_model=AuthResponse)
def admin_login(payload: AdminLoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    user = get_user_by_username(db, payload.username)
    if user is None or user.role != "admin" or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    add_login_log(db, user=user, ip_address=get_client_ip(request))
    return issue_auth_response(user)


@router.get("/interests", response_model=InterestOptionsResponse)
def read_interest_options(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InterestOptionsResponse:
    return InterestOptionsResponse(interests=list_interest_options(db))


@router.get("/me", response_model=UserInfo)
def read_me(current_user: User = Depends(get_current_user)) -> UserInfo:
    return build_user_info(current_user)


@router.patch("/me", response_model=UserInfo)
def update_me(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> UserInfo:
    if payload.interests is not None:
        allowed_interests = set(list_interest_options(db))
        invalid = [interest for interest in payload.interests if interest not in allowed_interests]
        if invalid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid interest selection")
    user = update_visitor_profile(
        db,
        current_user,
        nickname=payload.nickname,
        interests=payload.interests,
    )
    return build_user_info(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> Response:
    if not current_user.password_hash or not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different")
    update_password(db, current_user, payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def detect_image_extension(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return None


@router.post("/avatar", response_model=UserInfo, include_in_schema=False)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> UserInfo:
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Avatar exceeds 5 MB")
    extension = detect_image_extension(content)
    if extension is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PNG, JPEG and WebP are supported")

    filename = f"user-{current_user.id}-{uuid4().hex}{extension}"
    target = avatar_directory / filename
    target.write_bytes(content)

    previous_filename = Path(current_user.avatar_url).name if current_user.avatar_url else None
    user = update_avatar(db, current_user, f"/uploads/avatars/{filename}")
    if previous_filename and previous_filename != filename:
        previous_path = avatar_directory / previous_filename
        if previous_path.is_file():
            previous_path.unlink()
    return build_user_info(user)
