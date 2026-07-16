from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy import desc, distinct, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.spot import (
    RouteFeedback,
    RoutePlan,
    RouteRecommendationSetting,
    RouteSpot,
    ScenicSpot,
    SpotMediaAsset,
    VisitorBehaviorRecord,
)
from app.models.user import LoginLog, User
from app.schemas.routes import RouteFeedbackCreate, RouteRecommendRequest, RouteRecommendationSettingUpdate


DEFAULT_ROUTE_SETTINGS = {
    "tag_match_weight": 100,
    "priority_weight": 1.0,
    "max_spots": 12,
    "include_service_points": False,
}


def parse_interest_terms(interest: str) -> list[str]:
    return [term.strip().lower() for term in re.split(r"[,，、;/\s]+", interest) if term.strip()]


def matching_tags(spot: ScenicSpot, interest: str) -> list[str]:
    terms = parse_interest_terms(interest)
    return [
        tag.name
        for tag in spot.tags
        if any(term == tag.name.lower() or term in tag.name.lower() or tag.name.lower() in term for term in terms)
    ]


def get_route_settings(db: Session) -> RouteRecommendationSetting | None:
    return db.get(RouteRecommendationSetting, 1)


def serialize_route_settings(setting: RouteRecommendationSetting | None) -> dict:
    if setting is None:
        return {**DEFAULT_ROUTE_SETTINGS, "updated_at": None}
    return {
        "tag_match_weight": setting.tag_match_weight,
        "priority_weight": float(setting.priority_weight),
        "max_spots": setting.max_spots,
        "include_service_points": setting.include_service_points,
        "updated_at": setting.updated_at,
    }


def update_route_settings(db: Session, payload: RouteRecommendationSettingUpdate) -> RouteRecommendationSetting:
    setting = get_route_settings(db)
    if setting is None:
        setting = RouteRecommendationSetting(id=1)
        db.add(setting)
    setting.tag_match_weight = payload.tag_match_weight
    setting.priority_weight = Decimal(str(payload.priority_weight))
    setting.max_spots = payload.max_spots
    setting.include_service_points = payload.include_service_points
    db.commit()
    db.refresh(setting)
    return setting


def score_spot(spot: ScenicSpot, interest: str, settings: dict, preference: str) -> tuple[float, int, int]:
    matches = len(matching_tags(spot, interest))
    priority_weight = float(settings["priority_weight"])
    if preference == "priority":
        priority_weight *= 2
    score = matches * int(settings["tag_match_weight"]) + spot.priority * priority_weight
    if preference == "more_spots":
        score += max(0, 480 - spot.recommended_duration_minutes) / 10
    return (score, -spot.recommended_duration_minutes if preference == "more_spots" else spot.priority, -spot.id)


def build_route_reason(interest: str, selected: list[ScenicSpot], had_tag_match: bool, preference: str) -> str:
    names = "、".join(spot.name for spot in selected)
    preference_text = {
        "balanced": "结合你的兴趣和游玩时长",
        "priority": "优先安排代表性景点",
        "more_spots": "在可用时长内安排更多景点",
    }[preference]
    if had_tag_match:
        return f"根据你选择的“{interest}”，{preference_text}，为你安排：{names}。"
    return f"根据本次游玩时长和景点特色，为你安排：{names}。"


def recommend_route(db: Session, user: User, payload: RouteRecommendRequest) -> RoutePlan:
    setting_model = get_route_settings(db)
    settings = serialize_route_settings(setting_model)
    scenic_area = payload.scenic_area.strip()
    stmt = (
        select(ScenicSpot)
        .options(selectinload(ScenicSpot.tags))
        .where(ScenicSpot.status == "enabled", ScenicSpot.scenic_area == scenic_area)
    )
    if not settings["include_service_points"]:
        stmt = stmt.where(ScenicSpot.spot_type != "service")
    spots = list(db.scalars(stmt))

    start_spot = next((spot for spot in spots if spot.id == payload.start_spot_id), None)
    if payload.start_spot_id is not None and start_spot is None:
        raise ValueError("所选起点暂不可用，请重新选择。")

    ranked = sorted(
        (spot for spot in spots if spot.id != payload.start_spot_id),
        key=lambda spot: score_spot(spot, payload.interest, settings, payload.preference),
        reverse=True,
    )
    selected: list[ScenicSpot] = []
    total_duration = 0
    if start_spot is not None:
        if start_spot.recommended_duration_minutes > payload.duration_minutes:
            raise ValueError("当前游玩时长不足以游览所选起点，请增加游玩时长。")
        selected.append(start_spot)
        total_duration = start_spot.recommended_duration_minutes

    for spot in ranked:
        if len(selected) >= int(settings["max_spots"]):
            break
        if total_duration + spot.recommended_duration_minutes > payload.duration_minutes:
            continue
        selected.append(spot)
        total_duration += spot.recommended_duration_minutes

    if not selected:
        raise ValueError("当前游玩时长不足，请增加游玩时长后重试。")

    had_tag_match = any(matching_tags(spot, payload.interest) for spot in selected)
    route_plan = RoutePlan(
        user_id=user.id,
        start_spot_id=payload.start_spot_id,
        scenic_area=scenic_area,
        interest=payload.interest.strip(),
        preference=payload.preference,
        duration_minutes=payload.duration_minutes,
        total_duration_minutes=total_duration,
        reason=build_route_reason(payload.interest.strip(), selected, had_tag_match, payload.preference),
    )
    db.add(route_plan)
    db.flush()

    for index, spot in enumerate(selected, start=1):
        matches = matching_tags(spot, payload.interest)
        basis = f"符合你的{'、'.join(matches)}偏好" if matches else "适合纳入本次行程"
        if index == 1 and payload.start_spot_id == spot.id:
            basis = f"从你选择的起点出发；{basis}"
        db.add(
            RouteSpot(
                route_plan_id=route_plan.id,
                spot_id=spot.id,
                sequence=index,
                stay_minutes=spot.recommended_duration_minutes,
                reason=f"第 {index} 站安排 {spot.name}，{basis}，建议停留 {spot.recommended_duration_minutes} 分钟。",
            )
        )

    db.commit()
    return get_route_plan(db, route_plan.id, user) or route_plan


def route_load_options():
    return (
        selectinload(RoutePlan.route_spots).selectinload(RouteSpot.spot).selectinload(ScenicSpot.tags),
        selectinload(RoutePlan.feedback),
    )


def get_route_plan(db: Session, route_id: int, user: User) -> RoutePlan | None:
    return db.scalar(select(RoutePlan).options(*route_load_options()).where(RoutePlan.id == route_id, RoutePlan.user_id == user.id))


def create_feedback(db: Session, route_plan: RoutePlan, user: User, payload: RouteFeedbackCreate) -> RouteFeedback:
    feedback = route_plan.feedback
    if feedback is None:
        feedback = RouteFeedback(route_plan_id=route_plan.id, user_id=user.id, rating=payload.rating, comment=payload.comment)
        db.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.comment = payload.comment
    db.commit()
    db.refresh(feedback)
    return feedback


def list_admin_routes(db: Session, *, interest: str | None = None, rating: int | None = None) -> list[dict]:
    stmt = (
        select(
            RoutePlan,
            User.nickname,
            func.count(distinct(RouteSpot.id)).label("spot_count"),
            RouteFeedback.rating,
            RouteFeedback.comment,
        )
        .outerjoin(User, User.id == RoutePlan.user_id)
        .outerjoin(RouteSpot, RouteSpot.route_plan_id == RoutePlan.id)
        .outerjoin(RouteFeedback, RouteFeedback.route_plan_id == RoutePlan.id)
        .group_by(RoutePlan.id, User.nickname, RouteFeedback.rating, RouteFeedback.comment)
    )
    if interest:
        stmt = stmt.where(RoutePlan.interest.ilike(f"%{interest.strip()}%"))
    if rating is not None:
        stmt = stmt.where(RouteFeedback.rating == rating)
    rows = db.execute(stmt.order_by(RoutePlan.created_at.desc(), RoutePlan.id.desc())).all()
    return [
        {
            "id": plan.id,
            "user_id": plan.user_id,
            "visitor_name": nickname,
            "scenic_area": plan.scenic_area,
            "interest": plan.interest,
            "start_spot_id": plan.start_spot_id,
            "preference": plan.preference,
            "duration_minutes": plan.duration_minutes,
            "total_duration_minutes": plan.total_duration_minutes,
            "spot_count": spot_count,
            "rating": feedback_rating,
            "comment": comment,
            "created_at": plan.created_at,
        }
        for plan, nickname, spot_count, feedback_rating, comment in rows
    ]


def get_analytics_overview(db: Session) -> dict:
    average_rating = db.scalar(select(func.avg(RouteFeedback.rating)))
    behavior_average = db.scalar(select(func.avg(VisitorBehaviorRecord.satisfaction)))
    return {
        "login_count": db.scalar(select(func.count(LoginLog.id))) or 0,
        "spot_count": db.scalar(select(func.count(ScenicSpot.id))) or 0,
        "enabled_spot_count": db.scalar(select(func.count(ScenicSpot.id)).where(ScenicSpot.status == "enabled")) or 0,
        "media_count": db.scalar(select(func.count(SpotMediaAsset.id))) or 0,
        "route_count": db.scalar(select(func.count(RoutePlan.id))) or 0,
        "feedback_count": db.scalar(select(func.count(RouteFeedback.id))) or 0,
        "average_rating": round(float(average_rating), 2) if average_rating is not None else None,
        "behavior_record_count": db.scalar(select(func.count(VisitorBehaviorRecord.id))) or 0,
        "behavior_visitor_count": db.scalar(select(func.count(distinct(VisitorBehaviorRecord.tourist_id)))) or 0,
        "behavior_average_satisfaction": round(float(behavior_average), 2) if behavior_average is not None else None,
    }


def get_route_analytics(db: Session) -> dict:
    total_routes = db.scalar(select(func.count(RoutePlan.id))) or 0
    feedback_count = db.scalar(select(func.count(RouteFeedback.id))) or 0
    daily_rows = db.execute(
        select(func.date(RoutePlan.created_at), func.count(RoutePlan.id))
        .group_by(func.date(RoutePlan.created_at))
        .order_by(func.date(RoutePlan.created_at))
    ).all()
    interest_rows = db.execute(
        select(RoutePlan.interest, func.count(RoutePlan.id).label("count"))
        .group_by(RoutePlan.interest)
        .order_by(desc("count"), RoutePlan.interest)
        .limit(10)
    ).all()
    rating_rows = db.execute(
        select(RouteFeedback.rating, func.count(RouteFeedback.id)).group_by(RouteFeedback.rating).order_by(RouteFeedback.rating)
    ).all()
    requested_avg = db.scalar(select(func.avg(RoutePlan.duration_minutes)))
    planned_avg = db.scalar(select(func.avg(RoutePlan.total_duration_minutes)))
    return {
        "total_routes": total_routes,
        "feedback_rate": round(feedback_count / total_routes, 4) if total_routes else 0,
        "average_requested_minutes": round(float(requested_avg), 2) if requested_avg is not None else None,
        "average_planned_minutes": round(float(planned_avg), 2) if planned_avg is not None else None,
        "daily_routes": [{"date": row[0], "count": row[1]} for row in daily_rows],
        "popular_interests": [{"name": row[0], "count": row[1]} for row in interest_rows],
        "rating_distribution": [{"rating": row[0], "count": row[1]} for row in rating_rows],
    }


def get_spot_analytics(db: Session) -> dict:
    route_rows = db.execute(
        select(ScenicSpot.id, ScenicSpot.name, ScenicSpot.scenic_area, func.count(RouteSpot.id).label("selected_count"))
        .outerjoin(RouteSpot, RouteSpot.spot_id == ScenicSpot.id)
        .group_by(ScenicSpot.id)
        .order_by(desc("selected_count"), ScenicSpot.priority.desc(), ScenicSpot.id)
        .limit(20)
    ).all()
    behavior_rows = db.execute(
        select(
            VisitorBehaviorRecord.attraction_name,
            func.count(VisitorBehaviorRecord.id).label("visits"),
            func.count(distinct(VisitorBehaviorRecord.tourist_id)).label("unique_visitors"),
            func.avg(VisitorBehaviorRecord.stay_duration_hours),
            func.avg(VisitorBehaviorRecord.total_cost),
            func.avg(VisitorBehaviorRecord.satisfaction),
        )
        .group_by(VisitorBehaviorRecord.attraction_name)
        .order_by(desc("visits"), VisitorBehaviorRecord.attraction_name)
        .limit(20)
    ).all()
    return {
        "route_popular_spots": [
            {"spot_id": row[0], "name": row[1], "scenic_area": row[2], "selected_count": row[3]}
            for row in route_rows
        ],
        "behavior_attractions": [
            {
                "name": row[0],
                "visits": row[1],
                "unique_visitors": row[2],
                "average_stay_hours": round(float(row[3]), 2),
                "average_cost": round(float(row[4]), 2),
                "average_satisfaction": round(float(row[5]), 2),
            }
            for row in behavior_rows
        ],
    }
