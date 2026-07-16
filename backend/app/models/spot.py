from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ScenicSpot(Base):
    __tablename__ = "scenic_spots"
    __table_args__ = (
        CheckConstraint("status IN ('enabled', 'disabled')", name="ck_scenic_spots_status"),
        CheckConstraint("spot_type IN ('attraction', 'area', 'service')", name="ck_scenic_spots_type"),
        UniqueConstraint("external_id", name="uq_scenic_spots_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    scenic_area: Mapped[str] = mapped_column(String(120), index=True, nullable=False, default="灵山胜境")
    spot_type: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="attraction")
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    opening_hours: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    landscape_parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    cultural_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    highlights: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recommended_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="enabled")
    cover_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tags: Mapped[list["SpotTag"]] = relationship(
        back_populates="spot",
        cascade="all, delete-orphan",
        order_by="SpotTag.name",
    )
    media_assets: Mapped[list["SpotMediaAsset"]] = relationship(
        back_populates="spot",
        cascade="all, delete-orphan",
        order_by=lambda: (SpotMediaAsset.sort_order, SpotMediaAsset.id),
    )
    route_spots: Mapped[list["RouteSpot"]] = relationship(back_populates="spot")


class SpotTag(Base):
    __tablename__ = "spot_tags"
    __table_args__ = (UniqueConstraint("spot_id", "name", name="uq_spot_tags_spot_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    spot: Mapped[ScenicSpot] = relationship(back_populates="tags")


class SpotMediaAsset(Base):
    __tablename__ = "spot_media_assets"
    __table_args__ = (
        UniqueConstraint("spot_id", "url", name="uq_spot_media_spot_url"),
        CheckConstraint("media_type IN ('image', 'video', 'audio')", name="ck_spot_media_type"),
        CheckConstraint("status IN ('enabled', 'disabled')", name="ck_spot_media_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True, nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="enabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    spot: Mapped[ScenicSpot] = relationship(back_populates="media_assets")


class RouteRecommendationSetting(Base):
    __tablename__ = "route_recommendation_settings"
    __table_args__ = (
        CheckConstraint("tag_match_weight BETWEEN 0 AND 1000", name="ck_route_settings_tag_weight"),
        CheckConstraint("priority_weight BETWEEN 0 AND 100", name="ck_route_settings_priority_weight"),
        CheckConstraint("max_spots BETWEEN 1 AND 30", name="ck_route_settings_max_spots"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag_match_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    priority_weight: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=1)
    max_spots: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    include_service_points: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RoutePlan(Base):
    __tablename__ = "route_plans"
    __table_args__ = (CheckConstraint("preference IN ('balanced', 'priority', 'more_spots')", name="ck_route_plans_preference"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    start_spot_id: Mapped[int | None] = mapped_column(
        ForeignKey("scenic_spots.id", ondelete="SET NULL"), index=True, nullable=True
    )
    scenic_area: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    interest: Mapped[str] = mapped_column(String(100), nullable=False)
    preference: Mapped[str] = mapped_column(String(20), nullable=False, default="balanced")
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    route_spots: Mapped[list["RouteSpot"]] = relationship(
        back_populates="route_plan",
        cascade="all, delete-orphan",
        order_by="RouteSpot.sequence",
    )
    feedback: Mapped["RouteFeedback | None"] = relationship(
        back_populates="route_plan",
        cascade="all, delete-orphan",
        uselist=False,
    )


class RouteSpot(Base):
    __tablename__ = "route_spots"
    __table_args__ = (UniqueConstraint("route_plan_id", "sequence", name="uq_route_spots_plan_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_plan_id: Mapped[int] = mapped_column(ForeignKey("route_plans.id", ondelete="CASCADE"), index=True, nullable=False)
    spot_id: Mapped[int | None] = mapped_column(ForeignKey("scenic_spots.id", ondelete="SET NULL"), index=True, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stay_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    route_plan: Mapped[RoutePlan] = relationship(back_populates="route_spots")
    spot: Mapped[ScenicSpot | None] = relationship(back_populates="route_spots")


class RouteFeedback(Base):
    __tablename__ = "route_feedback"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_route_feedback_rating"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_plan_id: Mapped[int] = mapped_column(ForeignKey("route_plans.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    route_plan: Mapped[RoutePlan] = relationship(back_populates="feedback")


class VisitorBehaviorRecord(Base):
    __tablename__ = "visitor_behavior_records"
    __table_args__ = (
        CheckConstraint("satisfaction BETWEEN 1 AND 5", name="ck_behavior_satisfaction"),
        UniqueConstraint("source_record_key", name="uq_behavior_source_record_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_record_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    tourist_id: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    user_nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    attraction_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    attraction_content: Mapped[str] = mapped_column(Text, nullable=False)
    attraction_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    visit_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    stay_duration_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    ticket_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    food_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    shopping_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    transport_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    entertainment_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    group_size: Mapped[int] = mapped_column(Integer, nullable=False)
    satisfaction: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
