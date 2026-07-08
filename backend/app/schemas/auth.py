from __future__ import annotations

from pydantic import BaseModel, Field


class VisitorLoginRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=100)
    interest: str | None = Field(default=None, max_length=100)


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=100)


class UserInfo(BaseModel):
    id: int
    role: str
    username: str | None = None
    nickname: str | None = None
    interest: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo
