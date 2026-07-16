from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GuideSessionCreate(BaseModel):
    scenic_area_code: str = Field(min_length=2, max_length=64)


class GuideSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenic_area_id: int
    initial_rag_profile_id: int | None
    title: str | None
    created_at: datetime
    updated_at: datetime


class GuideMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    input_mode: str = Field(default="text", pattern=r"^(text|voice)$")


class GuideSourceOut(BaseModel):
    chunk_id: int
    document_id: int
    knowledge_base_id: int
    knowledge_base_name: str
    source_priority: int
    score: float
    spot_id: str | None
    spot_name: str | None
    section: str | None
    source_locator: str | None
    content: str


class GuideMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    input_mode: str | None
    content: str
    rag_profile_id: int | None
    sources: list[GuideSourceOut] | None
    answer_model: str | None
    answer_duration_ms: int | None
    status: str
    error_message: str | None
    created_at: datetime


class GuideConversationResponse(BaseModel):
    visitor_message: GuideMessageOut
    assistant_message: GuideMessageOut
    rag_profile_name: str
    knowledge_bases: list[str]


class AsrResponse(BaseModel):
    transcript: str
    model: str
    duration_ms: int


FeedbackTag = Literal["answer_accurate", "voice_natural", "avatar_preferred", "slow_response", "unresolved"]


class GuideFeedbackUpsert(BaseModel):
    rating: int = Field(ge=1, le=5)
    tags: list[FeedbackTag] = Field(default_factory=list, max_length=5)
    comment: str | None = Field(default=None, max_length=1000)


class GuideFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    guide_session_id: int
    rating: int
    tags: list[str]
    comment: str | None
    created_at: datetime
    updated_at: datetime
