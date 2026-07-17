from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.crud.guide import (
    create_guide_message,
    create_guide_session,
    get_route_spots,
    get_session_route_plan,
    get_guide_feedback,
    get_user_assistant_message,
    get_user_guide_session,
    list_guide_messages,
    list_user_guide_sessions,
    set_guide_route_context,
    touch_guide_session,
    upsert_guide_feedback,
)
from app.crud.avatar import default_scenic_avatar_config, get_scenic_avatar_config
from app.crud.knowledge import get_active_profile, get_scenic_area_by_code, get_scenic_area_by_id
from app.crud.insights import ensure_pending_insight, process_insight
from app.crud.routes import get_route_plan
from app.crud.tts import ensure_tts_provider_settings
from app.database import get_db
from app.models.avatar import TtsProviderSetting
from app.models.guide import GuideFeedback, GuideMessage, GuideSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.guide import (
    AsrResponse,
    GuideConversationResponse,
    GuideMessageCreate,
    GuideMessageOut,
    GuideRouteContextOut,
    GuideSessionContextUpdate,
    GuideSessionCreate,
    GuideSessionOut,
    GuideFeedbackOut,
    GuideFeedbackUpsert,
)
from app.services.guide_answer import GuideAnswerError, generate_guide_answer
from app.services.retrieval import RetrievalError, search_profile
from app.services.speech import SpeechError, recognize_speech
from app.services.streaming_speech import TtsRuntimeConfig, prepare_speech_stream


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


def _validate_route_context(
    db: Session,
    session: GuideSession,
    current_user: User,
    route_plan_id: int,
    current_spot_id: int,
):
    route_plan = get_route_plan(db, route_plan_id, current_user)
    if route_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="游览路线不存在")
    scenic_area = get_scenic_area_by_id(db, session.scenic_area_id)
    if scenic_area is None or route_plan.scenic_area != scenic_area.name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="游览路线不属于当前景区")
    route_spot = next(
        (item for item in route_plan.route_spots if item.spot_id == current_spot_id and item.spot is not None),
        None,
    )
    if route_spot is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="当前景点不在所选路线中")
    return route_plan, route_spot


def _serialize_route_context(route_plan: object, current_spot_id: int) -> dict:
    route_spots = [item for item in route_plan.route_spots if item.spot is not None]
    current = next(item for item in route_spots if item.spot_id == current_spot_id)
    return {
        "route_plan_id": route_plan.id,
        "interest": route_plan.interest,
        "current_spot_id": current_spot_id,
        "current_sequence": current.sequence,
        "total_spots": len(route_spots),
        "spots": [
            {
                "spot_id": item.spot_id,
                "sequence": item.sequence,
                "name": item.spot.name,
                "summary": item.spot.summary,
                "stay_minutes": item.stay_minutes,
                "reason": item.reason,
                "tags": [tag.name for tag in item.spot.tags],
            }
            for item in route_spots
        ],
    }


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
    route_plan_id = None
    current_spot_id = None
    if payload.route_plan_id is not None or payload.current_spot_id is not None:
        if payload.route_plan_id is None or payload.current_spot_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="路线和当前景点必须同时提供")
        route_plan, route_spot = _validate_route_context(
            db,
            GuideSession(user_id=current_user.id, scenic_area_id=scenic_area.id),
            current_user,
            payload.route_plan_id,
            payload.current_spot_id,
        )
        route_plan_id, current_spot_id = route_plan.id, route_spot.spot_id
    return create_guide_session(
        db,
        user_id=current_user.id,
        scenic_area=scenic_area,
        initial_rag_profile_id=profile.id,
        route_plan_id=route_plan_id,
        current_spot_id=current_spot_id,
    )


@router.get("/sessions", response_model=list[GuideSessionOut])
def read_sessions(
    current_user: User = Depends(require_visitor), db: Session = Depends(get_db)
) -> list[GuideSession]:
    return list_user_guide_sessions(db, current_user.id)


@router.get("/sessions/{session_id}", response_model=GuideSessionOut)
def read_session(
    session_id: int,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> GuideSession:
    return _session_or_404(db, session_id, current_user.id)


@router.patch("/sessions/{session_id}/context", response_model=GuideRouteContextOut)
def update_session_context(
    session_id: int,
    payload: GuideSessionContextUpdate,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> dict:
    session = _session_or_404(db, session_id, current_user.id)
    route_plan, route_spot = _validate_route_context(
        db, session, current_user, payload.route_plan_id, payload.current_spot_id
    )
    set_guide_route_context(
        db,
        session,
        route_plan_id=route_plan.id,
        current_spot_id=route_spot.spot_id,
    )
    return _serialize_route_context(route_plan, route_spot.spot_id)


@router.get("/sessions/{session_id}/context", response_model=GuideRouteContextOut)
def read_session_context(
    session_id: int,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> dict:
    session = _session_or_404(db, session_id, current_user.id)
    route_plan = get_session_route_plan(db, session)
    if route_plan is None or session.current_spot_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前会话尚未绑定游览路线")
    route_plan = get_route_plan(db, route_plan.id, current_user)
    if route_plan is None or not any(item.spot_id == session.current_spot_id for item in route_plan.route_spots):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前行程上下文已失效")
    return _serialize_route_context(route_plan, session.current_spot_id)


@router.get("/sessions/{session_id}/messages", response_model=list[GuideMessageOut])
def read_session_messages(
    session_id: int,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> list[GuideMessage]:
    _session_or_404(db, session_id, current_user.id)
    return list_guide_messages(db, session_id)


@router.get("/sessions/{session_id}/feedback", response_model=GuideFeedbackOut)
def read_session_feedback(
    session_id: int,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> GuideFeedback | Response:
    _session_or_404(db, session_id, current_user.id)
    feedback = get_guide_feedback(db, session_id)
    return feedback if feedback is not None else Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/feedback", response_model=GuideFeedbackOut)
def submit_session_feedback(
    session_id: int,
    payload: GuideFeedbackUpsert,
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> GuideFeedback:
    session = _session_or_404(db, session_id, current_user.id)
    has_answer = any(message.role == "assistant" for message in list_guide_messages(db, session.id))
    if not has_answer:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先完成至少一次导览问答再评价")
    comment = payload.comment.strip() if payload.comment and payload.comment.strip() else None
    return upsert_guide_feedback(
        db,
        session,
        current_user.id,
        rating=payload.rating,
        tags=list(payload.tags),
        comment=comment,
    )


@router.post("/sessions/{session_id}/messages", response_model=GuideConversationResponse)
def create_message(
    session_id: int,
    payload: GuideMessageCreate,
    background_tasks: BackgroundTasks,
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
        route_plan = get_session_route_plan(db, session)
        route_spots = get_route_spots(db, route_plan.id) if route_plan is not None else []
        available_route_spots = [item for item in route_spots if item.spot is not None]
        current_route_spot = next(
            (item for item in available_route_spots if item.spot_id == session.current_spot_id),
            None,
        )
        retrieval_query = payload.content.strip()
        route_context = None
        interests = route_plan.interest if route_plan is not None else (
            current_user.visitor_profile.interest if current_user.visitor_profile else None
        )
        if route_plan is not None and current_route_spot is not None:
            itinerary = " → ".join(item.spot.name for item in available_route_spots)
            route_context = (
                f"路线 #{route_plan.id}；当前第 {current_route_spot.sequence}/{len(available_route_spots)} 站："
                f"{current_route_spot.spot.name}；完整行程：{itinerary}。"
                "讲解时优先回应游客兴趣，并说明与本次行程的联系；不要虚构交通距离或开放状态。"
            )
            retrieval_query = f"{current_route_spot.spot.name} {retrieval_query}"
        result = search_profile(db, scenic_area, profile, retrieval_query, None, current_user.id)
        hits = result["hits"]
        if not isinstance(hits, list):
            raise GuideAnswerError("检索结果格式异常")
        answer = generate_guide_answer(
            query=payload.content.strip(),
            hits=hits,
            scenic_area_name=scenic_area.name,
            profile_name=profile.name,
            history=history,
            visitor_interests=interests,
            route_context=route_context,
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
    insight = ensure_pending_insight(db, session, visitor_message, assistant_message)
    background_tasks.add_task(process_insight, insight.id)
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
    try:
        if content_type and not content_type.startswith("audio/"):
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Please upload an audio file")
        audio = await file.read(settings.guide_max_audio_bytes + 1)
    finally:
        await file.close()
    if len(audio) > settings.guide_max_audio_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="录音文件不能超过 6 MB")
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
    avatar_variant_id: int | None = Query(default=None),
    current_user: User = Depends(require_visitor),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    message = get_user_assistant_message(db, message_id, current_user.id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guide answer not found")
    if message.status != "success":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="This answer cannot be spoken")
    session = _session_or_404(db, message.session_id, current_user.id)
    avatar_config = (
        get_scenic_avatar_config(db, session.scenic_area_id, avatar_variant_id, enabled_only=True)
        if avatar_variant_id is not None
        else default_scenic_avatar_config(db, session.scenic_area_id)
    )
    if avatar_variant_id is not None and avatar_config is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="所选数字人未在当前景区上架")
    provider_settings = ensure_tts_provider_settings(db)
    enabled = {item.provider: item for item in provider_settings if item.is_enabled}
    default_provider = next((item for item in provider_settings if item.is_default and item.is_enabled), None)
    fallback_provider = next((item for item in provider_settings if item.is_fallback and item.is_enabled), None)
    human = avatar_config.avatar_variant.digital_human if avatar_config is not None else None
    selected_provider = enabled.get(human.tts_provider) if human is not None else default_provider
    if selected_provider is None:
        selected_provider = default_provider
    if selected_provider is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="没有可用的语音服务")

    def runtime(item: TtsProviderSetting) -> TtsRuntimeConfig:
        return TtsRuntimeConfig(
            provider=item.provider,
            model=item.model,
            default_voice=item.default_voice,
            first_chunk_timeout_ms=item.first_chunk_timeout_ms,
        )

    try:
        prepared = await prepare_speech_stream(
            message.content,
            primary=runtime(selected_provider),
            fallback=runtime(fallback_provider) if fallback_provider is not None else None,
            voice=human.tts_voice if human is not None and selected_provider.provider == human.tts_provider else None,
            instructions=human.tts_instructions if human is not None else None,
        )
    except SpeechError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return StreamingResponse(
        prepared.chunks,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Audio-Format": "pcm_s16le",
            "X-Audio-Sample-Rate": str(prepared.sample_rate),
            "X-TTS-Provider": prepared.provider,
        },
    )
