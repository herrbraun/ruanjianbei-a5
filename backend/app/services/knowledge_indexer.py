from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeEmbedding
from app.services.embedding import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, embed_documents
from app.services.knowledge_parser import parse_document


UPLOAD_DIRECTORY = Path(__file__).resolve().parents[2] / "uploads" / "knowledge"


def storage_path(stored_filename: str) -> Path:
    return UPLOAD_DIRECTORY / stored_filename


def save_upload(content: bytes, content_hash: str, original_filename: str) -> str:
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    safe_name = Path(original_filename).name
    stored_filename = f"{content_hash[:16]}_{safe_name}"
    storage_path(stored_filename).write_bytes(content)
    return stored_filename


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def delete_stored_upload(stored_filename: str) -> None:
    upload_root = UPLOAD_DIRECTORY.resolve()
    path = storage_path(stored_filename).resolve()
    if path.parent != upload_root:
        raise ValueError("资料存储路径不安全")
    path.unlink(missing_ok=True)


def index_document(db: Session, document_id: int) -> KnowledgeDocument:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise ValueError("资料不存在")
    document.status = "indexing"
    document.error_message = None
    db.commit()

    try:
        data = storage_path(document.stored_filename).read_bytes()
        parsed_chunks = parse_document(data, document.original_filename, document.mime_type)
        document.chunk_count = len(parsed_chunks)
        document.embedding_count = 0
        db.commit()

        def update_progress(completed: int, _: int) -> None:
            progress_document = db.get(KnowledgeDocument, document_id)
            if progress_document is None:
                raise ValueError("资料已被删除，索引任务终止")
            progress_document.embedding_count = completed
            db.commit()

        vectors = embed_documents(
            (chunk.content for chunk in parsed_chunks),
            on_progress=update_progress,
        )
        if len(vectors) != len(parsed_chunks):
            raise RuntimeError("向量数量与切块数量不一致")

        # Prepare all remote work before replacing current index. The replace itself is one transaction.
        db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
        db.flush()
        for ordinal, (chunk, vector) in enumerate(zip(parsed_chunks, vectors), start=1):
            row = KnowledgeChunk(
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                spot_id=chunk.spot_id,
                spot_name=chunk.spot_name,
                section=chunk.section,
                ordinal=ordinal,
                content=chunk.content,
                source_locator=chunk.source_locator,
                content_hash=content_sha256(chunk.content.encode("utf-8")),
            )
            db.add(row)
            db.flush()
            db.add(
                KnowledgeEmbedding(
                    chunk_id=row.id,
                    embedding_model=EMBEDDING_MODEL,
                    dimensions=EMBEDDING_DIMENSIONS,
                    embedding=vector,
                )
            )
        document.status = "indexed"
        document.chunk_count = len(parsed_chunks)
        document.embedding_count = len(vectors)
        document.indexed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        db.rollback()
        document = db.get(KnowledgeDocument, document_id)
        if document is None:
            raise
        document.status = "failed"
        document.error_message = str(exc)[:2000]
        db.commit()
        db.refresh(document)
        return document


def index_document_background(document_id: int) -> None:
    db = SessionLocal()
    try:
        index_document(db, document_id)
    finally:
        db.close()
