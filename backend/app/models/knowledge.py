from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# The persisted embedding representation must not vary with a runtime setting.
# PostgreSQL can store a numeric array without any extension; SQLite keeps the
# same Python list as JSON for the test/local fallback.  pgvector, when
# available, is only a retrieval accelerator and is applied at query time.
EMBEDDING_STORAGE_TYPE = JSON().with_variant(ARRAY(Float), "postgresql")


class ScenicArea(Base):
    __tablename__ = "scenic_areas"
    __table_args__ = (Index("ix_scenic_areas_code", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    rag_profiles: Mapped[list["RagProfile"]] = relationship(back_populates="scenic_area", cascade="all, delete-orphan")


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (Index("ix_knowledge_bases_code", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    documents: Mapped[list["KnowledgeDocument"]] = relationship(back_populates="knowledge_base", cascade="all, delete-orphan")


class RagProfile(Base):
    __tablename__ = "rag_profiles"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_rag_profiles_status"),
        Index(
            "uq_rag_profiles_one_active_per_scenic",
            "scenic_area_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenic_area_id: Mapped[int] = mapped_column(ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'text-embedding-v4'"))
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1024"))
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    rerank_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    scenic_area: Mapped[ScenicArea] = relationship(back_populates="rag_profiles")
    knowledge_base_bindings: Mapped[list["RagProfileKnowledgeBase"]] = relationship(back_populates="rag_profile", cascade="all, delete-orphan")


class RagProfileKnowledgeBase(Base):
    __tablename__ = "rag_profile_knowledge_bases"
    __table_args__ = (UniqueConstraint("rag_profile_id", "knowledge_base_id", name="uq_rag_profile_knowledge_base"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rag_profile_id: Mapped[int] = mapped_column(ForeignKey("rag_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    retrieval_priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    rag_profile: Mapped[RagProfile] = relationship(back_populates="knowledge_base_bindings")
    knowledge_base: Mapped[KnowledgeBase] = relationship()


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'indexing', 'indexed', 'failed')", name="ck_knowledge_documents_status"),
        UniqueConstraint("knowledge_base_id", "content_hash", name="uq_knowledge_documents_base_hash"),
        Index("ix_knowledge_documents_base_status", "knowledge_base_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    embedding_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    knowledge_base: Mapped[KnowledgeBase] = relationship(back_populates="documents")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_knowledge_chunks_document_ordinal"),
        Index("ix_knowledge_chunks_base_spot", "knowledge_base_id", "spot_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    spot_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    spot_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
    embedding: Mapped["KnowledgeEmbedding | None"] = relationship(back_populates="chunk", cascade="all, delete-orphan", uselist=False)


class KnowledgeEmbedding(Base):
    __tablename__ = "knowledge_embeddings"
    __table_args__ = (Index("ix_knowledge_embeddings_chunk_id", "chunk_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False, unique=True)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'text-embedding-v4'"))
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1024"))
    embedding: Mapped[Any] = mapped_column(EMBEDDING_STORAGE_TYPE, nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    chunk: Mapped[KnowledgeChunk] = relationship(back_populates="embedding")


class RagQueryLog(Base):
    __tablename__ = "rag_query_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenic_area_id: Mapped[int] = mapped_column(ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False, index=True)
    rag_profile_id: Mapped[int | None] = mapped_column(ForeignKey("rag_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    hits: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'success'"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
