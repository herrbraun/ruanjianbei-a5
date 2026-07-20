from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,32}$"


def validate_password_bytes(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("password must not exceed 72 bytes")
    return password


class VisitorRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=64)

    _password_bytes = field_validator("password")(validate_password_bytes)


class VisitorLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=64)


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=100)


class GuestSessionRequest(BaseModel):
    guest_key: str | None = Field(default=None, min_length=1, max_length=256)


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=100)
    interests: list[str] | None = Field(default=None, min_length=1, max_length=8)

    @field_validator("nickname")
    @classmethod
    def strip_nickname(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not normalized:
            raise ValueError("at least one interest is required")
        if len(",".join(normalized)) > 100:
            raise ValueError("selected interests are too long")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> "ProfileUpdateRequest":
        if self.nickname is None and self.interests is None:
            raise ValueError("nickname or interests is required")
        return self


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=8, max_length=64)

    _new_password_bytes = field_validator("new_password")(validate_password_bytes)


class AdminPasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=12, max_length=64)

    _password_bytes = field_validator("current_password", "new_password")(validate_password_bytes)


class UsernameAvailabilityResponse(BaseModel):
    available: bool
    suggestions: list[str] = Field(default_factory=list)


class InterestOptionsResponse(BaseModel):
    interests: list[str]


class UserInfo(BaseModel):
    id: int
    role: str
    username: str | None = None
    nickname: str | None = None
    avatar_url: str | None = None
    interest: str | None = None
    interests: list[str] = Field(default_factory=list)
    needs_interest_setup: bool = False
    is_guest: bool = False


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo


class GuestAuthResponse(AuthResponse):
    guest_key: str | None = None
