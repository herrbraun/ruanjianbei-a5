from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.crud.knowledge import (
    activate_profile,
    create_knowledge_base,
    create_profile,
    create_scenic_area,
    delete_document,
    get_document,
    get_knowledge_base,
    get_profile,
    get_scenic_area_by_id,
    list_documents,
    list_knowledge_bases,
    list_profiles,
    list_scenic_areas,
)
from app.database import get_db
from app.models.knowledge import KnowledgeDocument, RagProfile, RagProfileKnowledgeBase
from app.models.user import User
from app.routers.auth import require_admin
from app.schemas.knowledge import (
    ChunkOut,
    DocumentOut,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    RagProfileCreate,
    RagProfileOut,
    RagSearchPreviewRequest,
    RagSearchPreviewResponse,
    ScenicAreaCreate,
    ScenicAreaOut,
)
from app.services.knowledge_indexer import content_sha256, delete_stored_upload, index_document_background, save_upload
from app.services.rag_answer import AnswerGenerationError, generate_rag_answer
from app.services.retrieval import RetrievalError, search_profile


router = APIRouter(prefix="/admin", tags=["knowledge"])
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_SUFFIXES = {".docx", ".txt", ".pdf"}


def _conflict_or_raise(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc


@router.get("/scenic-areas", response_model=list[ScenicAreaOut])
def read_scenic_areas(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[ScenicAreaOut]:
    return list_scenic_areas(db)


@router.post("/scenic-areas", response_model=ScenicAreaOut, status_code=status.HTTP_201_CREATED)
def add_scenic_area(payload: ScenicAreaCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> ScenicAreaOut:
    try:
        return create_scenic_area(db, **payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="景区编码已存在") from exc


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseOut])
def read_knowledge_bases(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[KnowledgeBaseOut]:
    return list_knowledge_bases(db)


@router.post("/knowledge-bases", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
def add_knowledge_base(payload: KnowledgeBaseCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> KnowledgeBaseOut:
    try:
        return create_knowledge_base(db, **payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="知识库编码已存在") from exc


@router.get("/rag-profiles", response_model=list[RagProfileOut])
def read_profiles(scenic_area_id: int | None = None, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[RagProfileOut]:
    return list_profiles(db, scenic_area_id)


@router.post("/rag-profiles", response_model=RagProfileOut, status_code=status.HTTP_201_CREATED)
def add_profile(payload: RagProfileCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> RagProfileOut:
    if get_scenic_area_by_id(db, payload.scenic_area_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="景区不存在")
    seen_bases: set[int] = set()
    bindings: list[RagProfileKnowledgeBase] = []
    for item in payload.knowledge_bases:
        if item.knowledge_base_id in seen_bases:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不能重复绑定同一知识库")
        if get_knowledge_base(db, item.knowledge_base_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        seen_bases.add(item.knowledge_base_id)
        bindings.append(RagProfileKnowledgeBase(**item.model_dump()))
    profile_values = payload.model_dump(exclude={"knowledge_bases"})
    profile = RagProfile(**profile_values)
    try:
        return create_profile(db, profile, bindings)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="创建 RAG Profile 失败") from exc


@router.post("/rag-profiles/{profile_id}/activate", response_model=RagProfileOut)
def activate_rag_profile(profile_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> RagProfileOut:
    profile = get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG Profile 不存在")
    try:
        return activate_profile(db, profile)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="切换正式 Profile 失败") from exc


@router.post("/knowledge/documents", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    knowledge_base_id: int = Form(...),
    source_priority: int = Form(default=0),
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DocumentOut:
    if get_knowledge_base(db, knowledge_base_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    filename = Path(file.filename or "").name
    if not filename or Path(filename).suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 DOCX、TXT 和 PDF 文件")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="单个文件不能超过 20 MB")
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="上传文件为空")
    digest = content_sha256(content)
    existing = db.query(KnowledgeDocument).filter_by(knowledge_base_id=knowledge_base_id, content_hash=digest).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"重复文件已存在（资料 ID：{existing.id}）")
    stored_filename = save_upload(content, digest, filename)
    document = KnowledgeDocument(
        knowledge_base_id=knowledge_base_id,
        original_filename=filename,
        stored_filename=stored_filename,
        mime_type=file.content_type or "application/octet-stream",
        content_hash=digest,
        source_priority=source_priority,
        status="pending",
    )
    db.add(document)
    _conflict_or_raise(db, "重复文件已存在")
    db.refresh(document)
    background_tasks.add_task(index_document_background, document.id)
    return document


@router.get("/knowledge/documents", response_model=list[DocumentOut])
def read_documents(knowledge_base_id: int | None = None, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[DocumentOut]:
    return list_documents(db, knowledge_base_id)


@router.post("/knowledge/documents/{document_id}/index", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
def reindex_document(document_id: int, background_tasks: BackgroundTasks, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> DocumentOut:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料不存在")
    if document.status in {"pending", "indexing"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="资料正在索引，请勿重复提交")
    document.status = "pending"
    document.error_message = None
    db.commit()
    db.refresh(document)
    background_tasks.add_task(index_document_background, document.id)
    return document


@router.delete("/knowledge/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(document_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料不存在")
    if document.status in {"pending", "indexing"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="资料正在索引，完成或失败后才能删除")
    stored_filename = document.stored_filename
    delete_document(db, document)
    try:
        delete_stored_upload(stored_filename)
    except OSError:
        # Database records, chunks and embeddings are already removed. A stale ignored upload
        # is safer than reporting a failed database deletion and inviting repeated requests.
        pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/knowledge/documents/{document_id}/chunks", response_model=list[ChunkOut])
def read_document_chunks(document_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[ChunkOut]:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资料不存在")
    return sorted(document.chunks, key=lambda item: item.ordinal)


@router.post("/rag/search-preview", response_model=RagSearchPreviewResponse)
def preview_search(payload: RagSearchPreviewRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> RagSearchPreviewResponse:
    scenic_area = get_scenic_area_by_id(db, payload.scenic_area_id)
    profile = get_profile(db, payload.rag_profile_id)
    if scenic_area is None or profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="景区或 RAG Profile 不存在")
    try:
        retrieval = search_profile(db, scenic_area, profile, payload.query, payload.top_k)
    except RetrievalError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    try:
        answer = generate_rag_answer(
            query=payload.query,
            hits=retrieval["hits"],
            scenic_area_name=scenic_area.name,
            profile_name=profile.name,
        )
        return RagSearchPreviewResponse(
            **retrieval,
            ai_answer=answer.content,
            answer_model=answer.model,
            answer_duration_ms=answer.duration_ms,
            answer_status="success",
        )
    except AnswerGenerationError as exc:
        return RagSearchPreviewResponse(
            **retrieval,
            answer_model=settings.llm_chat_model,
            answer_status="failed",
            answer_error=str(exc),
        )
