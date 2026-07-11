"""add multi-scenic RAG knowledge platform

Revision ID: 202607110001
Revises: 202607100001
Create Date: 2026-07-11 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "202607110001"
down_revision = "202607100001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenic_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_scenic_areas_code", "scenic_areas", ["code"])
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_knowledge_bases_code", "knowledge_bases", ["code"])
    op.create_table(
        "rag_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scenic_area_id", sa.Integer(), sa.ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("embedding_model", sa.String(length=100), nullable=False, server_default=sa.text("'text-embedding-v4'")),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False, server_default=sa.text("1024")),
        sa.Column("top_k", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("rerank_model", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_rag_profiles_status"),
    )
    op.create_index("ix_rag_profiles_scenic_area_id", "rag_profiles", ["scenic_area_id"])
    op.create_index(
        "uq_rag_profiles_one_active_per_scenic",
        "rag_profiles",
        ["scenic_area_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "rag_profile_knowledge_bases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rag_profile_id", sa.Integer(), sa.ForeignKey("rag_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("retrieval_priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("rag_profile_id", "knowledge_base_id", name="uq_rag_profile_knowledge_base"),
    )
    op.create_index("ix_rag_profile_knowledge_bases_rag_profile_id", "rag_profile_knowledge_bases", ["rag_profile_id"])
    op.create_index("ix_rag_profile_knowledge_bases_knowledge_base_id", "rag_profile_knowledge_bases", ["knowledge_base_id"])
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("knowledge_base_id", sa.Integer(), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("embedding_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'indexing', 'indexed', 'failed')", name="ck_knowledge_documents_status"),
        sa.UniqueConstraint("knowledge_base_id", "content_hash", name="uq_knowledge_documents_base_hash"),
    )
    op.create_index("ix_knowledge_documents_knowledge_base_id", "knowledge_documents", ["knowledge_base_id"])
    op.create_index("ix_knowledge_documents_base_status", "knowledge_documents", ["knowledge_base_id", "status"])
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("spot_id", sa.String(length=100), nullable=True),
        sa.Column("spot_name", sa.String(length=160), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_knowledge_chunks_document_ordinal"),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_knowledge_base_id", "knowledge_chunks", ["knowledge_base_id"])
    op.create_index("ix_knowledge_chunks_base_spot", "knowledge_chunks", ["knowledge_base_id", "spot_id"])
    op.create_table(
        "knowledge_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("embedding_model", sa.String(length=100), nullable=False, server_default=sa.text("'text-embedding-v4'")),
        sa.Column("dimensions", sa.Integer(), nullable=False, server_default=sa.text("1024")),
        sa.Column("embedding", sa.JSON().with_variant(sa.ARRAY(sa.Float()), "postgresql"), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_embeddings_chunk_id", "knowledge_embeddings", ["chunk_id"])
    op.create_table(
        "rag_query_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scenic_area_id", sa.Integer(), sa.ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rag_profile_id", sa.Integer(), sa.ForeignKey("rag_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("hits", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'success'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_rag_query_logs_scenic_area_id", "rag_query_logs", ["scenic_area_id"])
    op.create_index("ix_rag_query_logs_rag_profile_id", "rag_query_logs", ["rag_profile_id"])
    op.create_index("ix_rag_query_logs_user_id", "rag_query_logs", ["user_id"])

    op.execute("""
        INSERT INTO scenic_areas (code, name, description) VALUES
        ('lingshan', '灵山胜境', '灵山胜境示范景区')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO knowledge_bases (code, name, description) VALUES
        ('lingshan-structured', '灵山结构化景点资料库', '景点基础信息、开放时间与演艺安排'),
        ('lingshan-culture', '灵山历史文化资料库', '历史、文化和导览叙述资料')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO rag_profiles (scenic_area_id, name, status)
        SELECT id, '灵山正式版 RAG', 'active' FROM scenic_areas WHERE code = 'lingshan'
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO rag_profile_knowledge_bases (rag_profile_id, knowledge_base_id, retrieval_priority)
        SELECT profile.id, base.id,
               CASE WHEN base.code = 'lingshan-structured' THEN 100 ELSE 10 END
        FROM rag_profiles profile
        JOIN scenic_areas scenic ON scenic.id = profile.scenic_area_id
        JOIN knowledge_bases base ON base.code IN ('lingshan-structured', 'lingshan-culture')
        WHERE scenic.code = 'lingshan' AND profile.name = '灵山正式版 RAG'
        ON CONFLICT (rag_profile_id, knowledge_base_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("ix_rag_query_logs_user_id", table_name="rag_query_logs")
    op.drop_index("ix_rag_query_logs_rag_profile_id", table_name="rag_query_logs")
    op.drop_index("ix_rag_query_logs_scenic_area_id", table_name="rag_query_logs")
    op.drop_table("rag_query_logs")
    op.drop_index("ix_knowledge_embeddings_chunk_id", table_name="knowledge_embeddings")
    op.drop_table("knowledge_embeddings")
    op.drop_index("ix_knowledge_chunks_base_spot", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_knowledge_base_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_documents_base_status", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_knowledge_base_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_index("ix_rag_profile_knowledge_bases_knowledge_base_id", table_name="rag_profile_knowledge_bases")
    op.drop_index("ix_rag_profile_knowledge_bases_rag_profile_id", table_name="rag_profile_knowledge_bases")
    op.drop_table("rag_profile_knowledge_bases")
    op.drop_index("uq_rag_profiles_one_active_per_scenic", table_name="rag_profiles")
    op.drop_index("ix_rag_profiles_scenic_area_id", table_name="rag_profiles")
    op.drop_table("rag_profiles")
    op.drop_index("ix_knowledge_bases_code", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
    op.drop_index("ix_scenic_areas_code", table_name="scenic_areas")
    op.drop_table("scenic_areas")
