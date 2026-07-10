from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScenicAreaCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    is_enabled: bool = True


class ScenicAreaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: str | None
    is_enabled: bool


class KnowledgeBaseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    is_enabled: bool = True


class KnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: str | None
    is_enabled: bool


class ProfileKnowledgeBaseBind(BaseModel):
    knowledge_base_id: int
    is_enabled: bool = True
    retrieval_priority: int = Field(default=0, ge=-1000, le=1000)


class RagProfileCreate(BaseModel):
    scenic_area_id: int
    name: str = Field(min_length=1, max_length=120)
    status: str = Field(default="draft", pattern=r"^(draft|active)$")
    top_k: int = Field(default=5, ge=1, le=20)
    rerank_model: str | None = Field(default=None, max_length=100)
    knowledge_bases: list[ProfileKnowledgeBaseBind] = Field(default_factory=list)


class ProfileKnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    knowledge_base_id: int
    is_enabled: bool
    retrieval_priority: int
    knowledge_base: KnowledgeBaseOut | None = None


class RagProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scenic_area_id: int
    name: str
    status: str
    embedding_model: str
    embedding_dimensions: int
    top_k: int
    rerank_model: str | None
    knowledge_base_bindings: list[ProfileKnowledgeBaseOut] = Field(default_factory=list)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    knowledge_base_id: int
    original_filename: str
    mime_type: str
    content_hash: str
    source_priority: int
    status: str
    error_message: str | None
    chunk_count: int
    embedding_count: int
    created_at: datetime
    indexed_at: datetime | None


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    knowledge_base_id: int
    spot_id: str | None
    spot_name: str | None
    section: str | None
    ordinal: int
    content: str
    source_locator: str | None


class RagSearchRequest(BaseModel):
    scenic_area_code: str = Field(min_length=2, max_length=64)
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class RagSearchPreviewRequest(BaseModel):
    scenic_area_id: int
    rag_profile_id: int
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class RagSearchHit(BaseModel):
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


class RagSearchResponse(BaseModel):
    scenic_area_code: str
    rag_profile_id: int
    rag_profile_name: str
    knowledge_bases: list[str]
    hits: list[RagSearchHit]


class RagSearchPreviewResponse(RagSearchResponse):
    ai_answer: str | None = None
    answer_model: str | None = None
    answer_duration_ms: int | None = None
    answer_status: str
    answer_error: str | None = None
