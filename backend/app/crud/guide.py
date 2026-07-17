from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.guide import GuideFeedback, GuideMessage, GuideSession
from app.models.knowledge import ScenicArea
from app.models.spot import RoutePlan, RouteSpot


def create_guide_session(
    db: Session,
    *,
    user_id: int,
    scenic_area: ScenicArea,
    initial_rag_profile_id: int | None,
    route_plan_id: int | None = None,
    current_spot_id: int | None = None,
) -> GuideSession:
    session = GuideSession(
        user_id=user_id,
        scenic_area_id=scenic_area.id,
        initial_rag_profile_id=initial_rag_profile_id,
        route_plan_id=route_plan_id,
        current_spot_id=current_spot_id,
        title=scenic_area.name,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def set_guide_route_context(
    db: Session,
    session: GuideSession,
    *,
    route_plan_id: int,
    current_spot_id: int,
) -> None:
    session.route_plan_id = route_plan_id
    session.current_spot_id = current_spot_id
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()
    db.refresh(session)


def get_session_route_plan(db: Session, session: GuideSession) -> RoutePlan | None:
    if session.route_plan_id is None:
        return None
    return db.get(RoutePlan, session.route_plan_id)


def get_route_spots(db: Session, route_plan_id: int) -> list[RouteSpot]:
    statement = (
        select(RouteSpot)
        .options(selectinload(RouteSpot.spot))
        .where(RouteSpot.route_plan_id == route_plan_id)
        .order_by(RouteSpot.sequence)
    )
    return list(db.scalars(statement))


def list_user_guide_sessions(db: Session, user_id: int) -> list[GuideSession]:
    statement = (
        select(GuideSession)
        .where(GuideSession.user_id == user_id)
        .order_by(GuideSession.updated_at.desc(), GuideSession.id.desc())
    )
    return list(db.scalars(statement))


def get_user_guide_session(db: Session, session_id: int, user_id: int) -> GuideSession | None:
    return db.scalar(select(GuideSession).where(GuideSession.id == session_id, GuideSession.user_id == user_id))


def list_guide_messages(db: Session, session_id: int) -> list[GuideMessage]:
    statement = select(GuideMessage).where(GuideMessage.session_id == session_id).order_by(GuideMessage.id)
    return list(db.scalars(statement))


def create_guide_message(
    db: Session,
    *,
    session_id: int,
    role: str,
    content: str,
    input_mode: str | None = None,
    rag_profile_id: int | None = None,
    sources: list[dict[str, object]] | None = None,
    answer_model: str | None = None,
    answer_duration_ms: int | None = None,
    status: str = "success",
    error_message: str | None = None,
) -> GuideMessage:
    message = GuideMessage(
        session_id=session_id,
        role=role,
        content=content,
        input_mode=input_mode,
        rag_profile_id=rag_profile_id,
        sources=sources,
        answer_model=answer_model,
        answer_duration_ms=answer_duration_ms,
        status=status,
        error_message=error_message,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def touch_guide_session(db: Session, session: GuideSession) -> None:
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()


def get_user_assistant_message(db: Session, message_id: int, user_id: int) -> GuideMessage | None:
    statement = (
        select(GuideMessage)
        .join(GuideSession, GuideSession.id == GuideMessage.session_id)
        .where(GuideMessage.id == message_id, GuideMessage.role == "assistant", GuideSession.user_id == user_id)
    )
    return db.scalar(statement)


def get_guide_feedback(db: Session, session_id: int) -> GuideFeedback | None:
    return db.scalar(select(GuideFeedback).where(GuideFeedback.guide_session_id == session_id))


def upsert_guide_feedback(
    db: Session,
    session: GuideSession,
    user_id: int,
    *,
    rating: int,
    tags: list[str],
    comment: str | None,
) -> GuideFeedback:
    feedback = get_guide_feedback(db, session.id)
    if feedback is None:
        feedback = GuideFeedback(
            guide_session_id=session.id,
            user_id=user_id,
            scenic_area_id=session.scenic_area_id,
            rating=rating,
            tags=tags,
            comment=comment,
        )
        db.add(feedback)
    else:
        feedback.rating = rating
        feedback.tags = tags
        feedback.comment = comment
    db.commit()
    db.refresh(feedback)
    return feedback
