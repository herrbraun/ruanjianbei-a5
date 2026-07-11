from __future__ import annotations

from math import sqrt
from time import perf_counter

from pgvector.sqlalchemy import Vector
from sqlalchemy import cast, func, literal, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.crud.knowledge import get_active_profile
from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeEmbedding, RagProfile, RagProfileKnowledgeBase, RagQueryLog, ScenicArea
from app.services.embedding import embed_query


class RetrievalError(RuntimeError):
    pass


def _json_cosine_distance(stored: object, query: list[float]) -> float:
    if not isinstance(stored, list) or len(stored) != len(query) or not stored:
        raise RetrievalError("知识库向量格式异常，请重新索引资料")
    try:
        dot_product = sum(float(left) * right for left, right in zip(stored, query))
        left_norm = sqrt(sum(float(value) ** 2 for value in stored))
        right_norm = sqrt(sum(value**2 for value in query))
    except (TypeError, ValueError) as exc:
        raise RetrievalError("知识库向量格式异常，请重新索引资料") from exc
    if not left_norm or not right_norm:
        raise RetrievalError("知识库包含空向量，请重新索引资料")
    return 1 - max(-1.0, min(1.0, dot_product / (left_norm * right_norm)))


def _pgvector_extension_is_available(db: Session) -> bool:
    return bool(db.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")))


def _pgvector_distance(vector: list[float]):
    # PostgreSQL arrays use {x,y}; pgvector accepts [x,y].  Convert at query
    # time so the stored column remains portable when the extension is absent.
    vector_text = literal("[") + func.array_to_string(KnowledgeEmbedding.embedding, ",") + literal("]")
    return cast(vector_text, Vector(1024)).cosine_distance(vector).label("distance")


def search_profile(db: Session, scenic_area: ScenicArea, profile: RagProfile, query: str, top_k: int | None, user_id: int | None = None) -> dict[str, object]:
    if profile.scenic_area_id != scenic_area.id:
        raise RetrievalError("RAG Profile 不属于所选景区")
    started = perf_counter()
    try:
        vector = embed_query(query)
        limit = top_k or profile.top_k
        base_statement = (
            select(KnowledgeChunk, KnowledgeDocument, KnowledgeBase, RagProfileKnowledgeBase.retrieval_priority)
            .join(KnowledgeEmbedding, KnowledgeEmbedding.chunk_id == KnowledgeChunk.id)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .join(KnowledgeBase, KnowledgeBase.id == KnowledgeChunk.knowledge_base_id)
            .join(RagProfileKnowledgeBase, RagProfileKnowledgeBase.knowledge_base_id == KnowledgeBase.id)
            .where(
                RagProfileKnowledgeBase.rag_profile_id == profile.id,
                RagProfileKnowledgeBase.is_enabled.is_(True),
                KnowledgeBase.is_enabled.is_(True),
                KnowledgeDocument.status == "indexed",
            )
        )
        if settings.uses_json_vector_backend:
            candidate_limit = settings.rag_json_candidate_limit
            candidate_rows = db.execute(
                base_statement.add_columns(KnowledgeEmbedding.embedding)
                .order_by(RagProfileKnowledgeBase.retrieval_priority.desc(), KnowledgeDocument.source_priority.desc())
                .limit(candidate_limit + 1)
            ).all()
            if len(candidate_rows) > candidate_limit:
                raise RetrievalError(
                    f"JSON 向量检索最多支持 {candidate_limit} 条候选资料；请缩小知识库范围或启用 pgvector"
                )
            rows = sorted(
                (
                    (chunk, document, base, _json_cosine_distance(embedding, vector), priority)
                    for chunk, document, base, priority, embedding in candidate_rows
                ),
                key=lambda row: (-row[4], -row[1].source_priority, row[3]),
            )[:limit]
        else:
            if not _pgvector_extension_is_available(db):
                raise RetrievalError("RAG_VECTOR_BACKEND=pgvector，但当前数据库未安装 vector 扩展；请安装 pgvector 或设置为 json")
            distance = _pgvector_distance(vector)
            pgvector_rows = db.execute(
                base_statement.add_columns(distance)
                .order_by(RagProfileKnowledgeBase.retrieval_priority.desc(), KnowledgeDocument.source_priority.desc(), distance.asc())
                .limit(limit)
            ).all()
            rows = [
                (chunk, document, base, row_distance, priority)
                for chunk, document, base, priority, row_distance in pgvector_rows
            ]
        hits = [
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "knowledge_base_id": base.id,
                "knowledge_base_name": base.name,
                "source_priority": document.source_priority,
                "score": max(0.0, min(1.0, 1.0 - float(row_distance))),
                "spot_id": chunk.spot_id,
                "spot_name": chunk.spot_name,
                "section": chunk.section,
                "source_locator": chunk.source_locator,
                "content": chunk.content,
            }
            for chunk, document, base, row_distance, _ in rows
        ]
        db.add(
            RagQueryLog(
                scenic_area_id=scenic_area.id,
                rag_profile_id=profile.id,
                user_id=user_id,
                query_text=query,
                filters={
                    "top_k": limit,
                    "knowledge_base_ids": [binding.knowledge_base_id for binding in profile.knowledge_base_bindings if binding.is_enabled],
                },
                hits=hits,
                duration_ms=round((perf_counter() - started) * 1000),
                status="success",
            )
        )
        db.commit()
        return {
            "scenic_area_code": scenic_area.code,
            "rag_profile_id": profile.id,
            "rag_profile_name": profile.name,
            "knowledge_bases": [binding.knowledge_base.name for binding in profile.knowledge_base_bindings if binding.is_enabled and binding.knowledge_base],
            "hits": hits,
        }
    except Exception as exc:
        db.rollback()
        db.add(
            RagQueryLog(
                scenic_area_id=scenic_area.id,
                rag_profile_id=profile.id,
                user_id=user_id,
                query_text=query,
                duration_ms=round((perf_counter() - started) * 1000),
                status="failed",
                error_message=str(exc)[:2000],
            )
        )
        db.commit()
        if isinstance(exc, RetrievalError):
            raise
        raise RetrievalError(str(exc)) from exc


def search_active_profile(db: Session, scenic_area: ScenicArea, query: str, top_k: int | None, user_id: int | None = None) -> dict[str, object]:
    profile = get_active_profile(db, scenic_area.id)
    if profile is None:
        raise RetrievalError("该景区尚未配置正式 RAG Profile")
    return search_profile(db, scenic_area, profile, query, top_k, user_id)
