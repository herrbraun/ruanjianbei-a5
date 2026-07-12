from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SpotMediaBase(BaseModel):
    spot_id: int = Field(gt=0)
    media_type: str = Field(pattern="^(image|video|audio)$")
    url: HttpUrl
    description: str | None = Field(default=None, max_length=255)
    sort_order: int = Field(default=0, ge=0, le=1000)
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$")


class SpotMediaCreate(SpotMediaBase):
    pass


class SpotMediaUpdate(SpotMediaBase):
    pass


class SpotMediaResponse(BaseModel):
    id: int
    spot_id: int
    spot_name: str | None = None
    media_type: str
    url: str
    description: str | None
    sort_order: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpotBase(BaseModel):
    external_id: str | None = Field(default=None, max_length=30)
    scenic_area: str = Field(default="灵山胜境", min_length=1, max_length=120)
    spot_type: str = Field(default="attraction", pattern="^(attraction|area|service)$")
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    location: str | None = Field(default=None, max_length=500)
    opening_hours: str | None = Field(default=None, max_length=1000)
    landscape_parameters: str | None = None
    cultural_context: str | None = None
    highlights: str | None = None
    notes: str | None = None
    source_name: str | None = Field(default=None, max_length=255)
    recommended_duration_minutes: int = Field(default=30, ge=5, le=480)
    priority: int = Field(default=0, ge=0, le=100)
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$")
    cover_image_url: HttpUrl | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)


class SpotCreate(SpotBase):
    pass


class SpotUpdate(SpotBase):
    pass


class SpotStatusUpdate(BaseModel):
    status: str = Field(pattern="^(enabled|disabled)$")


class SpotResponse(SpotBase):
    id: int
    media_assets: list[SpotMediaResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
