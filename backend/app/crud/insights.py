from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import desc, distinct, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.guide import GuideFeedback, GuideMessage, GuideMessageInsight, GuideSession
from app.services.interaction_insight import analyze_interaction


def ensure_pending_insight(db: Session, session: GuideSession, visitor: GuideMessage, assistant: GuideMessage | None) -> GuideMessageInsight:
    existing = db.scalar(select(GuideMessageInsight).where(GuideMessageInsight.visitor_message_id == visitor.id))
    if existing is not None:
        return existing
    row = GuideMessageInsight(
        scenic_area_id=session.scenic_area_id,
        guide_session_id=session.id,
        visitor_message_id=visitor.id,
        assistant_message_id=assistant.id if assistant else None,
        analysis_status="pending",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalar(select(GuideMessageInsight).where(GuideMessageInsight.visitor_message_id == visitor.id))
    db.refresh(row)
    return row


def recover_stale_insights(db: Session, stale_before: datetime) -> int:
    result = db.execute(
        update(GuideMessageInsight)
        .where(GuideMessageInsight.analysis_status == "processing", GuideMessageInsight.updated_at < stale_before)
        .values(analysis_status="pending", error_message="任务中断，等待重试")
    )
    db.commit()
    return result.rowcount or 0


def process_insight(insight_id: int) -> None:
    with SessionLocal() as db:
        row = db.get(GuideMessageInsight, insight_id)
        if row is None or row.analysis_status not in {"pending", "failed"}:
            return
        row.analysis_status = "processing"
        row.analysis_attempts += 1
        row.error_message = None
        db.commit()
        visitor = db.get(GuideMessage, row.visitor_message_id)
        assistant = db.get(GuideMessage, row.assistant_message_id) if row.assistant_message_id else None
        try:
            if visitor is None:
                raise ValueError("游客问题不存在")
            result = analyze_interaction(visitor.content, assistant.content if assistant else "", assistant.status if assistant else "failed")
            for field, value in result.model_dump().items():
                setattr(row, field, value)
            row.analysis_model = settings.insight_analysis_model
            row.analysis_status = "completed"
            row.analyzed_at = datetime.now(timezone.utc)
        except Exception as exc:
            row.analysis_status = "failed"
            row.error_message = str(exc)[:2000]
        db.commit()


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _period_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(start_date, time.min, SHANGHAI).astimezone(timezone.utc)
    end = datetime.combine(end_date + timedelta(days=1), time.min, SHANGHAI).astimezone(timezone.utc)
    return start, end


def _ratio(value: int, total: int) -> float:
    return round(value / total, 4) if total else 0.0


def _dashboard_metrics(db: Session, scenic_area_id: int, start: datetime, end: datetime) -> dict:
    session_filter = (GuideSession.scenic_area_id == scenic_area_id, GuideSession.created_at >= start, GuideSession.created_at < end)
    session_count = db.scalar(select(func.count(GuideSession.id)).where(*session_filter)) or 0
    service_visitors = db.scalar(select(func.count(distinct(GuideSession.user_id))).where(*session_filter)) or 0
    message_base = (GuideMessage.created_at >= start, GuideMessage.created_at < end, GuideSession.scenic_area_id == scenic_area_id)
    question_count = db.scalar(select(func.count(GuideMessage.id)).join(GuideSession).where(*message_base, GuideMessage.role == "user")) or 0
    answer_count = db.scalar(select(func.count(GuideMessage.id)).join(GuideSession).where(*message_base, GuideMessage.role == "assistant")) or 0
    success_count = db.scalar(select(func.count(GuideMessage.id)).join(GuideSession).where(*message_base, GuideMessage.role == "assistant", GuideMessage.status == "success")) or 0
    average_duration = db.scalar(select(func.avg(GuideMessage.answer_duration_ms)).join(GuideSession).where(*message_base, GuideMessage.role == "assistant", GuideMessage.status == "success"))
    insight_filter = (GuideMessageInsight.scenic_area_id == scenic_area_id, GuideMessageInsight.created_at >= start, GuideMessageInsight.created_at < end)
    completed = db.scalar(select(func.count(GuideMessageInsight.id)).where(*insight_filter, GuideMessageInsight.analysis_status == "completed")) or 0
    negative = db.scalar(select(func.count(GuideMessageInsight.id)).where(*insight_filter, GuideMessageInsight.analysis_status == "completed", GuideMessageInsight.sentiment == "negative")) or 0
    average_rating = db.scalar(select(func.avg(GuideFeedback.rating)).where(GuideFeedback.scenic_area_id == scenic_area_id, GuideFeedback.created_at >= start, GuideFeedback.created_at < end))
    return {
        "service_visitors": service_visitors,
        "session_count": session_count,
        "question_count": question_count,
        "answer_success_rate": _ratio(success_count, answer_count),
        "average_answer_duration_ms": round(float(average_duration), 2) if average_duration is not None else None,
        "average_rating": round(float(average_rating), 2) if average_rating is not None else None,
        "negative_rate": _ratio(negative, completed),
        "analysis_coverage_rate": _ratio(completed, question_count),
        "analysis_failed_count": max(0, question_count - completed),
    }


def get_guide_dashboard(db: Session, scenic_area_id: int, start_date: date, end_date: date) -> dict:
    start, end = _period_bounds(start_date, end_date)
    days = (end_date - start_date).days + 1
    previous_end_date = start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=days - 1)
    previous_start, previous_end = _period_bounds(previous_start_date, previous_end_date)
    insight_filter = (GuideMessageInsight.scenic_area_id == scenic_area_id, GuideMessageInsight.created_at >= start, GuideMessageInsight.created_at < end, GuideMessageInsight.analysis_status == "completed")

    popular = db.execute(
        select(GuideMessageInsight.normalized_question, func.count(GuideMessageInsight.id).label("count"))
        .where(*insight_filter, GuideMessageInsight.normalized_question.is_not(None))
        .group_by(GuideMessageInsight.normalized_question).order_by(desc("count")).limit(10)
    ).all()
    topics = db.execute(
        select(GuideMessageInsight.primary_topic, func.count(GuideMessageInsight.id).label("count"))
        .where(*insight_filter, GuideMessageInsight.primary_topic.is_not(None))
        .group_by(GuideMessageInsight.primary_topic).order_by(desc("count"))
    ).all()
    attention = db.scalars(
        select(GuideMessageInsight).where(
            GuideMessageInsight.scenic_area_id == scenic_area_id,
            GuideMessageInsight.created_at >= start,
            GuideMessageInsight.created_at < end,
            GuideMessageInsight.needs_attention.is_(True),
            GuideMessageInsight.resolution_status == "unresolved",
        ).order_by(GuideMessageInsight.created_at.desc()).limit(8)
    ).all()
    service_rows = db.execute(
        select(func.date(GuideSession.created_at), func.count(GuideSession.id), func.count(distinct(GuideSession.user_id)))
        .where(GuideSession.scenic_area_id == scenic_area_id, GuideSession.created_at >= start, GuideSession.created_at < end)
        .group_by(func.date(GuideSession.created_at)).order_by(func.date(GuideSession.created_at))
    ).all()
    sentiment_rows = db.execute(
        select(func.date(GuideMessageInsight.created_at), GuideMessageInsight.sentiment, func.count(GuideMessageInsight.id))
        .where(*insight_filter).group_by(func.date(GuideMessageInsight.created_at), GuideMessageInsight.sentiment)
    ).all()
    rating_rows = db.execute(
        select(func.date(GuideFeedback.created_at), func.avg(GuideFeedback.rating), func.count(GuideFeedback.id))
        .where(GuideFeedback.scenic_area_id == scenic_area_id, GuideFeedback.created_at >= start, GuideFeedback.created_at < end)
        .group_by(func.date(GuideFeedback.created_at)).order_by(func.date(GuideFeedback.created_at))
    ).all()
    sentiment_by_day: dict[str, dict[str, int | str]] = {}
    for day, sentiment, count in sentiment_rows:
        key = str(day)
        sentiment_by_day.setdefault(key, {"date": key, "positive": 0, "neutral": 0, "negative": 0})[sentiment] = count
    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "metrics": _dashboard_metrics(db, scenic_area_id, start, end),
        "previous_period": _dashboard_metrics(db, scenic_area_id, previous_start, previous_end),
        "service_trend": [{"date": str(row[0]), "sessions": row[1], "visitors": row[2]} for row in service_rows],
        "sentiment_trend": list(sentiment_by_day.values()),
        "satisfaction_trend": [{"date": str(row[0]), "average_rating": round(float(row[1]), 2), "count": row[2]} for row in rating_rows],
        "topic_distribution": [{"name": row[0], "count": row[1]} for row in topics],
        "popular_questions": [{"name": row[0], "count": row[1]} for row in popular],
        "attention_preview": [{"id": row.id, "normalized_question": row.normalized_question, "issue_type": row.issue_type, "sentiment": row.sentiment, "created_at": row.created_at} for row in attention],
    }
