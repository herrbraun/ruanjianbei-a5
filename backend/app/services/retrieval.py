from __future__ import annotations

from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.knowledge import get_active_profile
from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeEmbedding, RagProfile, RagProfileKnowledgeBase, RagQueryLog, ScenicArea
from app.services.embedding import embed_query


class RetrievalError(RuntimeError):
    pass


def search_profile(db: Session, scenic_area: ScenicArea, profile: RagProfile, query: str, top_k: int | None, user_id: int | None = None) -> dict[str, object]:
    if profile.scenic_area_id != scenic_area.id:
        raise RetrievalError("RAG Profile 不属于所选景区")
    started = perf_counter()
    try:
        vector = embed_query(query)
        limit = top_k or profile.top_k
        distance = KnowledgeEmbedding.embedding.cosine_distance(vector).label("distance")
        statement = (
            select(KnowledgeChunk, KnowledgeDocument, KnowledgeBase, distance, RagProfileKnowledgeBase.retrieval_priority)
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
            .order_by(RagProfileKnowledgeBase.retrieval_priority.desc(), KnowledgeDocument.source_priority.desc(), distance.asc())
            .limit(limit)
        )
        rows = db.execute(statement).all()
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
