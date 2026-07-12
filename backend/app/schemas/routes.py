from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class RouteRecommendRequest(BaseModel):
    interest: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(ge=15, le=480)
    start_spot_id: int | None = Field(default=None, gt=0)
    preference: str = Field(default="balanced", pattern="^(balanced|priority|more_spots)$")


class RouteSpotResponse(BaseModel):
    id: int
    spot_id: int | None
    sequence: int
    name: str
    summary: str
    location: str | None
    cover_image_url: str | None
    stay_minutes: int
    reason: str
    tags: list[str]


class RoutePlanResponse(BaseModel):
    id: int
    interest: str
    start_spot_id: int | None
    preference: str
    duration_minutes: int
    total_duration_minutes: int
    reason: str
    created_at: datetime
    spots: list[RouteSpotResponse]

    model_config = ConfigDict(from_attributes=True)


class RouteFeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class RouteFeedbackResponse(BaseModel):
    id: int
    route_plan_id: int
    rating: int
    comment: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RouteRecommendationSettingUpdate(BaseModel):
    tag_match_weight: int = Field(ge=0, le=1000)
    priority_weight: float = Field(ge=0, le=100)
    max_spots: int = Field(ge=1, le=30)
    include_service_points: bool


class RouteRecommendationSettingResponse(RouteRecommendationSettingUpdate):
    updated_at: datetime | None = None


class AdminRouteResponse(BaseModel):
    id: int
    user_id: int | None
    visitor_name: str | None
    interest: str
    start_spot_id: int | None
    preference: str
    duration_minutes: int
    total_duration_minutes: int
    spot_count: int
    rating: int | None
    comment: str | None
    created_at: datetime


class AnalyticsOverviewResponse(BaseModel):
    login_count: int
    spot_count: int
    enabled_spot_count: int
    media_count: int
    route_count: int
    feedback_count: int
    average_rating: float | None
    behavior_record_count: int
    behavior_visitor_count: int
    behavior_average_satisfaction: float | None


class NamedCount(BaseModel):
    name: str
    count: int


class DateCount(BaseModel):
    date: date
    count: int


class RatingCount(BaseModel):
    rating: int
    count: int


class RouteAnalyticsResponse(BaseModel):
    total_routes: int
    feedback_rate: float
    average_requested_minutes: float | None
    average_planned_minutes: float | None
    daily_routes: list[DateCount]
    popular_interests: list[NamedCount]
    rating_distribution: list[RatingCount]


class SpotRouteStat(BaseModel):
    spot_id: int
    name: str
    scenic_area: str
    selected_count: int


class BehaviorAttractionStat(BaseModel):
    name: str
    visits: int
    unique_visitors: int
    average_stay_hours: float
    average_cost: float
    average_satisfaction: float


class SpotAnalyticsResponse(BaseModel):
    route_popular_spots: list[SpotRouteStat]
    behavior_attractions: list[BehaviorAttractionStat]
