from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token, verify_password
from app.crud.user import add_login_log, create_visitor, get_user_by_id, get_user_by_username
from app.database import get_db
from app.models.user import User
from app.schemas.auth import AdminLoginRequest, AuthResponse, UserInfo, VisitorLoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


def build_user_info(user: User) -> UserInfo:
    return UserInfo(
        id=user.id,
        role=user.role,
        username=user.username,
        nickname=user.nickname,
        interest=user.visitor_profile.interest if user.visitor_profile else None,
    )


def issue_auth_response(user: User) -> AuthResponse:
    token = create_access_token({"user_id": user.id, "role": user.role})
    return AuthResponse(access_token=token, token_type="bearer", user=build_user_info(user))


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


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


@router.post("/visitor-login", response_model=AuthResponse)
def visitor_login(payload: VisitorLoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    user = create_visitor(db, nickname=payload.nickname, interest=payload.interest)
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


@router.get("/me", response_model=UserInfo)
def read_me(current_user: User = Depends(get_current_user)) -> UserInfo:
    return build_user_info(current_user)
