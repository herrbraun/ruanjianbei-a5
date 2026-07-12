from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.crud.routes import get_analytics_overview, get_route_analytics, get_spot_analytics
from app.database import get_db
from app.models.user import User
from app.routers.auth import require_admin
from app.schemas.routes import AnalyticsOverviewResponse, RouteAnalyticsResponse, SpotAnalyticsResponse

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


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
