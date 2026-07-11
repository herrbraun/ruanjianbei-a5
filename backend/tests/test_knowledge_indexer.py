from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.crud.knowledge import delete_document
from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeEmbedding, RagProfile, ScenicArea
from app.services.knowledge_indexer import content_sha256, index_document
from app.services.knowledge_parser import ParsedChunk
from app.services.retrieval import RetrievalError, search_profile


def _session():
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def test_document_hash_is_unique_per_knowledge_base() -> None:
    engine, db = _session()
    try:
        base = KnowledgeBase(code="hash-base", name="Hash Base")
        db.add(base)
        db.commit()
        digest = content_sha256(b"same content")
        db.add_all([
            KnowledgeDocument(knowledge_base_id=base.id, original_filename="a.txt", stored_filename="a.txt", mime_type="text/plain", content_hash=digest),
            KnowledgeDocument(knowledge_base_id=base.id, original_filename="b.txt", stored_filename="b.txt", mime_type="text/plain", content_hash=digest),
        ])
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("duplicate content hash must be rejected")
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_failed_reindex_keeps_previous_chunks() -> None:
    engine, db = _session()
    try:
        base = KnowledgeBase(code="retry-base", name="Retry Base")
        db.add(base)
        db.commit()
        document = KnowledgeDocument(knowledge_base_id=base.id, original_filename="guide.txt", stored_filename="guide.txt", mime_type="text/plain", content_hash="a" * 64, status="indexed", chunk_count=1, embedding_count=0)
        db.add(document)
        db.commit()
        db.add(KnowledgeChunk(document_id=document.id, knowledge_base_id=base.id, ordinal=1, content="previous indexed content", content_hash="b" * 64))
        db.commit()
        with TemporaryDirectory() as directory:
            source = Path(directory) / "guide.txt"
            source.write_text("replacement", encoding="utf-8")
            with patch("app.services.knowledge_indexer.storage_path", return_value=source), patch("app.services.knowledge_indexer.parse_document", side_effect=ValueError("bad document")):
                failed = index_document(db, document.id)
        assert failed.status == "failed"
        assert db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)).one().content == "previous indexed content"
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_indexing_reports_embedding_batch_progress() -> None:
    engine, db = _session()
    try:
        base = KnowledgeBase(code="progress-base", name="Progress Base")
        db.add(base)
        db.commit()
        document = KnowledgeDocument(
            knowledge_base_id=base.id,
            original_filename="guide.txt",
            stored_filename="guide.txt",
            mime_type="text/plain",
            content_hash="c" * 64,
        )
        db.add(document)
        db.commit()
        progress_values: list[int] = []

        def fake_embed(texts, on_progress=None):
            items = list(texts)
            assert on_progress is not None
            for completed in range(1, len(items) + 1):
                on_progress(completed, len(items))
                progress_values.append(db.get(KnowledgeDocument, document.id).embedding_count)
            return [[0.01] * 1024 for _ in items]

        with TemporaryDirectory() as directory:
            source = Path(directory) / "guide.txt"
            source.write_text("replacement", encoding="utf-8")
            with (
                patch("app.services.knowledge_indexer.storage_path", return_value=source),
                patch(
                    "app.services.knowledge_indexer.parse_document",
                    return_value=[ParsedChunk(content="first"), ParsedChunk(content="second")],
                ),
                patch("app.services.knowledge_indexer.embed_documents", side_effect=fake_embed),
            ):
                indexed = index_document(db, document.id)

        assert progress_values == [1, 2]
        assert indexed.status == "indexed"
        assert indexed.chunk_count == 2
        assert indexed.embedding_count == 2
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_deleting_indexed_document_cascades_chunks_and_embeddings() -> None:
    engine, db = _session()
    try:
        base = KnowledgeBase(code="delete-base", name="Delete Base")
        db.add(base)
        db.commit()
        document = KnowledgeDocument(
            knowledge_base_id=base.id,
            original_filename="indexed.txt",
            stored_filename="indexed.txt",
            mime_type="text/plain",
            content_hash="d" * 64,
            status="indexed",
            chunk_count=1,
            embedding_count=1,
        )
        db.add(document)
        db.commit()
        chunk = KnowledgeChunk(
            document_id=document.id,
            knowledge_base_id=base.id,
            ordinal=1,
            content="indexed content",
            content_hash="e" * 64,
        )
        db.add(chunk)
        db.commit()
        embedding = KnowledgeEmbedding(chunk_id=chunk.id, embedding=[0.01] * 1024)
        db.add(embedding)
        db.commit()
        document_id, chunk_id, embedding_id = document.id, chunk.id, embedding.id

        delete_document(db, document)

        assert db.get(KnowledgeDocument, document_id) is None
        assert db.get(KnowledgeChunk, chunk_id) is None
        assert db.get(KnowledgeEmbedding, embedding_id) is None
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_profile_cannot_search_another_scenic_area() -> None:
    engine, db = _session()
    try:
        first = ScenicArea(code="first", name="First")
        second = ScenicArea(code="second", name="Second")
        db.add_all([first, second])
        db.commit()
        profile = RagProfile(scenic_area_id=second.id, name="Second Profile", status="draft")
        db.add(profile)
        db.commit()
        try:
            search_profile(db, first, profile, "question", None)
        except RetrievalError as exc:
            assert "不属于所选景区" in str(exc)
        else:
            raise AssertionError("cross-scenic retrieval must be rejected")
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
