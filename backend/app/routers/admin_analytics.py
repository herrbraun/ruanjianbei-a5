from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crud.insights import get_guide_dashboard
from app.crud.knowledge import get_scenic_area_by_id
from app.crud.routes import get_analytics_overview, get_route_analytics, get_spot_analytics
from app.database import get_db
from app.models.user import User
from app.routers.auth import require_admin
from app.schemas.routes import AnalyticsOverviewResponse, RouteAnalyticsResponse, SpotAnalyticsResponse

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


@router.get("/guide")
def read_guide_dashboard(
    scenic_area_id: int = Query(gt=0),
    start_date: date = Query(),
    end_date: date = Query(),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if get_scenic_area_by_id(db, scenic_area_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="景区不存在")
    if start_date > end_date or (end_date - start_date).days > 365:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="日期范围无效或超过 366 天")
    return get_guide_dashboard(db, scenic_area_id, start_date, end_date)


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def read_analytics_overview(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return get_analytics_overview(db)


@router.get("/routes", response_model=RouteAnalyticsResponse)
def read_route_analytics(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return get_route_analytics(db)


@router.get("/spots", response_model=SpotAnalyticsResponse)
def read_spot_analytics(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return get_spot_analytics(db)
