from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DigitalHumanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    gender: str = Field(default="unspecified", pattern=r"^(female|male|unspecified)$")
    role_title: str = Field(min_length=1, max_length=120)
    introduction: str | None = Field(default=None, max_length=2000)
    tts_provider: str = Field(default="volcengine", pattern=r"^(volcengine|dashscope)$")
    tts_voice: str = Field(min_length=1, max_length=100)
    tts_instructions: str | None = Field(default=None, max_length=1000)


class DigitalHumanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    gender: str | None = Field(default=None, pattern=r"^(female|male|unspecified)$")
    role_title: str | None = Field(default=None, min_length=1, max_length=120)
    introduction: str | None = Field(default=None, max_length=2000)
    tts_provider: str | None = Field(default=None, pattern=r"^(volcengine|dashscope)$")
    tts_voice: str | None = Field(default=None, min_length=1, max_length=100)
    tts_instructions: str | None = Field(default=None, max_length=1000)
    is_enabled: bool | None = None


class AvatarVariantUpdate(BaseModel):
    outfit_name: str | None = Field(default=None, min_length=1, max_length=120)
    version: str | None = Field(default=None, min_length=1, max_length=40)
    thumbnail_url: str | None = Field(default=None, max_length=500)


class ScenicAvatarConfigUpdate(BaseModel):
    is_enabled: bool | None = None
    is_default: bool | None = None
    sort_order: int | None = Field(default=None, ge=-1000, le=1000)


class VoiceOptionOut(BaseModel):
    provider: str
    value: str
    label: str


class AvatarVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    digital_human_id: int
    outfit_name: str
    version: str
    original_filename: str
    file_size: int
    thumbnail_url: str | None
    validation_status: str
    created_at: datetime


class DigitalHumanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    gender: str
    role_title: str
    introduction: str | None
    tts_provider: str
    tts_voice: str
    tts_instructions: str | None
    is_enabled: bool
    variants: list[AvatarVariantOut] = Field(default_factory=list)


class ScenicAvatarOut(BaseModel):
    config_id: int
    scenic_area_id: int
    id: int
    digital_human_id: int
    name: str
    gender: str
    role_title: str
    introduction: str | None
    outfit_name: str
    version: str
    thumbnail_url: str | None
    file_size: int
    is_enabled: bool
    is_default: bool
    sort_order: int


class ScenicAvatarListOut(BaseModel):
    scenic_area_id: int
    default_variant_id: int | None
    avatars: list[ScenicAvatarOut]


class TtsProviderSettingUpdate(BaseModel):
    is_enabled: bool | None = None
    is_default: bool | None = None
    is_fallback: bool | None = None
    model: str | None = Field(default=None, min_length=1, max_length=120)
    default_voice: str | None = Field(default=None, min_length=1, max_length=100)
    first_chunk_timeout_ms: int | None = Field(default=None, ge=500, le=10000)


class TtsProviderSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    provider: str
    display_name: str
    is_enabled: bool
    is_default: bool
    is_fallback: bool
    model: str
    default_voice: str
    first_chunk_timeout_ms: int
    last_visitor_first_chunk_ms: int | None
    last_visitor_first_chunk_at: datetime | None
    configured: bool


class TtsProviderTestRequest(BaseModel):
    text: str = Field(default="欢迎来到灵山胜境，我是您的数字讲解员。", min_length=1, max_length=200)
    voice: str | None = Field(default=None, min_length=1, max_length=100)
