from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.insights import get_guide_dashboard, period_bounds, process_insight
from app.crud.knowledge import get_scenic_area_by_id
from app.database import get_db
from app.models.guide import GuideMessage, GuideMessageInsight, ScenicInsightReport
from app.models.user import User
from app.routers.auth import require_admin
from app.schemas.insights import ISSUE_TYPES, InsightReportCreate, InsightReportOut, InsightResolve
from app.services.insight_report import process_report

router = APIRouter(prefix="/admin", tags=["admin-insights"])


@router.get("/insights/messages")
def list_insight_messages(
    scenic_area_id: int = Query(gt=0), sentiment: str | None = None,
    issue_type: str | None = None, analysis_status: str | None = None,
    needs_attention: bool | None = None, resolution_status: str | None = None,
    start_date: date = Query(), end_date: date = Query(),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_admin), db: Session = Depends(get_db),
) -> dict:
    if get_scenic_area_by_id(db, scenic_area_id) is None:
        raise HTTPException(status_code=404, detail="景区不存在")
    if start_date > end_date or (end_date - start_date).days > 365:
        raise HTTPException(status_code=422, detail="日期范围无效或超过 366 天")
    if sentiment is not None and sentiment not in {"positive", "neutral", "negative"}:
        raise HTTPException(status_code=422, detail="情绪筛选值无效")
    if issue_type is not None and issue_type not in ISSUE_TYPES:
        raise HTTPException(status_code=422, detail="问题类型筛选值无效")
    if analysis_status is not None and analysis_status not in {"pending", "processing", "completed", "failed"}:
        raise HTTPException(status_code=422, detail="分析状态筛选值无效")
    if resolution_status is not None and resolution_status not in {"unresolved", "resolved"}:
        raise HTTPException(status_code=422, detail="处理状态筛选值无效")
    start, end = period_bounds(start_date, end_date)
    filters = [GuideMessageInsight.created_at >= start, GuideMessageInsight.created_at < end]
    for column, value in ((GuideMessageInsight.scenic_area_id, scenic_area_id), (GuideMessageInsight.sentiment, sentiment), (GuideMessageInsight.issue_type, issue_type), (GuideMessageInsight.analysis_status, analysis_status), (GuideMessageInsight.needs_attention, needs_attention), (GuideMessageInsight.resolution_status, resolution_status)):
        if value is not None: filters.append(column == value)
    total = db.scalar(select(func.count(GuideMessageInsight.id)).where(*filters)) or 0
    rows = db.scalars(select(GuideMessageInsight).where(*filters).order_by(GuideMessageInsight.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for row in rows:
        visitor = db.get(GuideMessage, row.visitor_message_id)
        assistant = db.get(GuideMessage, row.assistant_message_id) if row.assistant_message_id else None
        items.append({
            "id": row.id, "scenic_area_id": row.scenic_area_id, "normalized_question": row.normalized_question,
            "primary_topic": row.primary_topic, "intent": row.intent, "sentiment": row.sentiment,
            "sentiment_score": row.sentiment_score, "issue_type": row.issue_type, "needs_attention": row.needs_attention,
            "resolution_status": row.resolution_status, "analysis_status": row.analysis_status, "analysis_attempts": row.analysis_attempts,
            "error_message": row.error_message, "question": visitor.content if visitor else None,
            "answer": assistant.content if assistant else None, "created_at": row.created_at,
        })
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("/insights/messages/{insight_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_insight(insight_id: int, background_tasks: BackgroundTasks, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    row = db.get(GuideMessageInsight, insight_id)
    if row is None: raise HTTPException(status_code=404, detail="洞察记录不存在")
    if row.analysis_status not in {"failed", "pending"}: raise HTTPException(status_code=409, detail="仅失败或待处理记录可重试")
    row.analysis_status = "pending"; row.error_message = None; db.commit()
    background_tasks.add_task(process_insight, row.id)
    return {"status": "pending"}


@router.post("/insights/messages/retry-failed", status_code=status.HTTP_202_ACCEPTED)
def retry_failed_insights(background_tasks: BackgroundTasks, scenic_area_id: int = Query(gt=0), _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    stmt = select(GuideMessageInsight).where(GuideMessageInsight.analysis_status == "failed")
    stmt = stmt.where(GuideMessageInsight.scenic_area_id == scenic_area_id)
    rows = list(db.scalars(stmt.limit(100)))
    for row in rows: row.analysis_status = "pending"; row.error_message = None
    db.commit()
    for row in rows: background_tasks.add_task(process_insight, row.id)
    return {"scheduled": len(rows)}


@router.patch("/insights/messages/{insight_id}/resolve")
def resolve_insight(insight_id: int, payload: InsightResolve, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    row = db.get(GuideMessageInsight, insight_id)
    if row is None: raise HTTPException(status_code=404, detail="洞察记录不存在")
    row.resolution_status = "resolved" if payload.resolved else "unresolved"
    row.resolved_at = datetime.now(timezone.utc) if payload.resolved else None
    row.resolved_by_user_id = admin.id if payload.resolved else None
    db.commit()
    return {"id": row.id, "resolution_status": row.resolution_status}


@router.post("/insight-reports", response_model=InsightReportOut, status_code=status.HTTP_202_ACCEPTED)
def create_insight_report(payload: InsightReportCreate, background_tasks: BackgroundTasks, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> ScenicInsightReport:
    if get_scenic_area_by_id(db, payload.scenic_area_id) is None: raise HTTPException(status_code=404, detail="景区不存在")
    if payload.period_start > payload.period_end: raise HTTPException(status_code=422, detail="报告日期范围无效")
    dashboard = get_guide_dashboard(db, payload.scenic_area_id, payload.period_start, payload.period_end)
    snapshot = {**dashboard["metrics"], "top_topics": dashboard["topic_distribution"], "popular_questions": dashboard["popular_questions"], "sentiment_trend": dashboard["sentiment_trend"], "satisfaction_trend": dashboard["satisfaction_trend"]}
    report = ScenicInsightReport(scenic_area_id=payload.scenic_area_id, period_type=payload.period_type, period_start=payload.period_start, period_end=payload.period_end, metrics_snapshot=snapshot, generation_status="pending", created_by_user_id=admin.id)
    db.add(report); db.commit(); db.refresh(report)
    background_tasks.add_task(process_report, report.id)
    return report


@router.get("/insight-reports", response_model=list[InsightReportOut])
def list_insight_reports(scenic_area_id: int = Query(gt=0), _: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[ScenicInsightReport]:
    stmt = select(ScenicInsightReport).where(ScenicInsightReport.scenic_area_id == scenic_area_id).order_by(ScenicInsightReport.created_at.desc())
    return list(db.scalars(stmt))


@router.get("/insight-reports/{report_id}", response_model=InsightReportOut)
def read_insight_report(report_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> ScenicInsightReport:
    report = db.get(ScenicInsightReport, report_id)
    if report is None: raise HTTPException(status_code=404, detail="报告不存在")
    return report
