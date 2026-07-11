from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.crud.guide import (
    create_guide_message,
    create_guide_session,
    get_user_assistant_message,
    get_user_guide_session,
    list_guide_messages,
    list_user_guide_sessions,
    touch_guide_session,
)
from app.crud.knowledge import get_active_profile, get_scenic_area_by_code, get_scenic_area_by_id
from app.database import get_db
from app.models.guide import GuideMessage, GuideSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.guide import (
    AsrResponse,
    GuideConversationResponse,
    GuideMessageCreate,
    GuideMessageOut,
    GuideSessionCreate,
    GuideSessionOut,
)
from app.services.guide_answer import GuideAnswerError, generate_guide_answer
from app.services.retrieval import RetrievalError, search_profile
from app.services.speech import SpeechError, recognize_speech, synthesize_speech


router = APIRouter(prefix="/guide", tags=["guide"])


def require_visitor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "visitor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Visitor permission required")
    return current_user


def _session_or_404(db: Session, session_id: int, user_id: int) -> GuideSession:
    session = get_user_guide_session(db, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guide session not found")
    return session


def _message_history(messages: Sequence[GuideMessage]) -> list[tuple[str, str]]:
    return [(message.role, message.content) for message in messages if message.status == "success"]


def _profile_knowledge_base_names(profile: object) -> list[str]:
    bindings = getattr(profile, "knowledge_base_bindings", [])
    return [
        binding.knowledge_base.name
        for binding in bindings
        if binding.is_enabled and binding.knowledge_base is not None
    ]


@router.post("/sessions", response_model=GuideSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: GuideSessionCreate,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> GuideSession:
    scenic_area = get_scenic_area_by_code(db, payload.scenic_area_code)
    if scenic_area is None or not scenic_area.is_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenic area not found or disabled")
    profile = get_active_profile(db, scenic_area.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="This scenic area has no active RAG Profile")
    return create_guide_session(
        db,
        user_id=current_user.id,
        scenic_area=scenic_area,
        initial_rag_profile_id=profile.id,
    )


@router.get("/sessions", response_model=list[GuideSessionOut])
def read_sessions(
    current_user: User = Depends(require_visitor), db: Session = Depends(get_db)
) -> list[GuideSession]:
    return list_user_guide_sessions(db, current_user.id)


@router.get("/sessions/{session_id}/messages", response_model=list[GuideMessageOut])
def read_session_messages(
    session_id: int,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> list[GuideMessage]:
    _session_or_404(db, session_id, current_user.id)
    return list_guide_messages(db, session_id)


@router.post("/sessions/{session_id}/messages", response_model=GuideConversationResponse)
def create_message(
    session_id: int,
    payload: GuideMessageCreate,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> GuideConversationResponse:
    session = _session_or_404(db, session_id, current_user.id)
    scenic_area = get_scenic_area_by_id(db, session.scenic_area_id)
    if scenic_area is None or not scenic_area.is_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenic area not found or disabled")

    profile = get_active_profile(db, scenic_area.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="This scenic area has no active RAG Profile")

    history = _message_history(list_guide_messages(db, session.id))
    visitor_message = create_guide_message(
        db,
        session_id=session.id,
        role="user",
        content=payload.content.strip(),
        input_mode=payload.input_mode,
    )

    try:
        result = search_profile(db, scenic_area, profile, payload.content.strip(), None, current_user.id)
        hits = result["hits"]
        if not isinstance(hits, list):
            raise GuideAnswerError("检索结果格式异常")
        answer = generate_guide_answer(
            query=payload.content.strip(),
            hits=hits,
            scenic_area_name=scenic_area.name,
            profile_name=profile.name,
            history=history,
        )
        assistant_message = create_guide_message(
            db,
            session_id=session.id,
            role="assistant",
            content=answer.content,
            rag_profile_id=profile.id,
            sources=hits,
            answer_model=answer.model,
            answer_duration_ms=answer.duration_ms,
        )
    except (RetrievalError, GuideAnswerError) as exc:
        assistant_message = create_guide_message(
            db,
            session_id=session.id,
            role="assistant",
            content="抱歉，当前暂时无法完成这次导览回答，请稍后再试。",
            rag_profile_id=profile.id,
            sources=[],
            status="failed",
            error_message=str(exc)[:2000],
        )
    touch_guide_session(db, session)
    return GuideConversationResponse(
        visitor_message=visitor_message,
        assistant_message=assistant_message,
        rag_profile_name=profile.name,
        knowledge_bases=_profile_knowledge_base_names(profile),
    )


@router.post("/asr", response_model=AsrResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(require_visitor),
) -> AsrResponse:
    del current_user
    content_type = file.content_type
    if content_type and not content_type.startswith("audio/"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Please upload an audio file")
    try:
        audio = await file.read()
    finally:
        await file.close()
    try:
        recognized = await run_in_threadpool(recognize_speech, audio, content_type)
    except SpeechError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return AsrResponse(
        transcript=recognized.transcript,
        model=recognized.model,
        duration_ms=recognized.duration_ms,
    )


@router.post("/messages/{message_id}/speech")
async def synthesize_message(
    message_id: int,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> Response:
    message = get_user_assistant_message(db, message_id, current_user.id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guide answer not found")
    if message.status != "success":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="This answer cannot be spoken")
    try:
        synthesized = await run_in_threadpool(synthesize_speech, message.content)
    except SpeechError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return Response(
        content=synthesized.audio,
        media_type=synthesized.media_type,
        headers={"Cache-Control": "no-store"},
    )
