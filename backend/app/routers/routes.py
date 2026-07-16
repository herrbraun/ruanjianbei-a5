from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud.routes import (
    create_feedback,
    get_route_plan,
    get_route_settings,
    list_admin_routes,
    recommend_route,
    serialize_route_settings,
    update_route_settings,
)
from app.database import get_db
from app.models.spot import RoutePlan, RouteSpot
from app.models.user import User
from app.routers.auth import get_current_user, require_admin
from app.schemas.routes import (
    AdminRouteResponse,
    RouteFeedbackCreate,
    RouteFeedbackResponse,
    RoutePlanResponse,
    RouteRecommendationSettingResponse,
    RouteRecommendationSettingUpdate,
    RouteRecommendRequest,
)

router = APIRouter(prefix="/routes", tags=["routes"])
admin_router = APIRouter(prefix="/admin/routes", tags=["admin-routes"])


def serialize_route_spot(route_spot: RouteSpot) -> dict:
    spot = route_spot.spot
    return {
        "id": route_spot.id,
        "spot_id": spot.id if spot else None,
        "sequence": route_spot.sequence,
        "name": spot.name if spot else "已删除景点",
        "summary": spot.summary if spot else "",
        "location": spot.location if spot else None,
        "cover_image_url": spot.cover_image_url if spot else None,
        "stay_minutes": route_spot.stay_minutes,
        "reason": route_spot.reason,
        "tags": [tag.name for tag in spot.tags] if spot else [],
    }


def serialize_route_plan(route_plan: RoutePlan) -> dict:
    return {
        "id": route_plan.id,
        "scenic_area": route_plan.scenic_area,
        "interest": route_plan.interest,
        "start_spot_id": route_plan.start_spot_id,
        "preference": route_plan.preference,
        "duration_minutes": route_plan.duration_minutes,
        "total_duration_minutes": route_plan.total_duration_minutes,
        "reason": route_plan.reason,
        "created_at": route_plan.created_at,
        "spots": [serialize_route_spot(route_spot) for route_spot in route_plan.route_spots],
    }


@router.post("/recommend", response_model=RoutePlanResponse, status_code=status.HTTP_201_CREATED)
def create_route_recommendation(
    payload: RouteRecommendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return serialize_route_plan(recommend_route(db, current_user, payload))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{route_id}", response_model=RoutePlanResponse)
def read_route(
    route_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    route_plan = get_route_plan(db, route_id, current_user)
    if route_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    return serialize_route_plan(route_plan)


@router.post("/{route_id}/feedback", response_model=RouteFeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_route_feedback(
    route_id: int,
    payload: RouteFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RouteFeedbackResponse:
    route_plan = get_route_plan(db, route_id, current_user)
    if route_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    return create_feedback(db, route_plan, current_user, payload)


@admin_router.get("", response_model=list[AdminRouteResponse])
def read_admin_routes(
    interest: str | None = None,
    rating: int | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    if rating is not None and rating not in range(1, 6):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rating must be between 1 and 5")
    return list_admin_routes(db, interest=interest, rating=rating)


@admin_router.get("/settings", response_model=RouteRecommendationSettingResponse)
def read_route_settings(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return serialize_route_settings(get_route_settings(db))


@admin_router.put("/settings", response_model=RouteRecommendationSettingResponse)
def write_route_settings(
    payload: RouteRecommendationSettingUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return serialize_route_settings(update_route_settings(db, payload))
