from __future__ import annotations

from datetime import date, datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class GuideSession(Base):
    __tablename__ = "guide_sessions"
    __table_args__ = (
        Index("ix_guide_sessions_user_updated", "user_id", "updated_at"),
        Index("ix_guide_sessions_scenic_area_id", "scenic_area_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scenic_area_id: Mapped[int] = mapped_column(ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False)
    initial_rag_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("rag_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    route_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("route_plans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    current_spot_id: Mapped[int | None] = mapped_column(
        ForeignKey("scenic_spots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="guide_sessions")
    messages: Mapped[list["GuideMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="GuideMessage.id"
    )


class GuideMessage(Base):
    __tablename__ = "guide_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_guide_messages_role"),
        CheckConstraint("input_mode IS NULL OR input_mode IN ('text', 'voice')", name="ck_guide_messages_input_mode"),
        CheckConstraint("status IN ('success', 'failed')", name="ck_guide_messages_status"),
        Index("ix_guide_messages_session_created", "session_id", "created_at"),
        Index("ix_guide_messages_rag_profile_id", "rag_profile_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("guide_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    input_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rag_profile_id: Mapped[int | None] = mapped_column(ForeignKey("rag_profiles.id", ondelete="SET NULL"), nullable=True)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    answer_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    answer_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'success'"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    session: Mapped[GuideSession] = relationship(back_populates="messages")


class GuideMessageInsight(Base):
    __tablename__ = "guide_message_insights"
    __table_args__ = (
        UniqueConstraint("visitor_message_id", name="uq_guide_message_insights_visitor_message"),
        CheckConstraint("analysis_status IN ('pending', 'processing', 'completed', 'failed')", name="ck_guide_message_insights_analysis_status"),
        CheckConstraint("sentiment IS NULL OR sentiment IN ('positive', 'neutral', 'negative')", name="ck_guide_message_insights_sentiment"),
        CheckConstraint("sentiment_score IS NULL OR (sentiment_score >= -1 AND sentiment_score <= 1)", name="ck_guide_message_insights_sentiment_score"),
        CheckConstraint("resolution_status IN ('unresolved', 'resolved')", name="ck_guide_message_insights_resolution_status"),
        Index("ix_guide_insights_scenic_created", "scenic_area_id", "created_at"),
        Index("ix_guide_insights_scenic_sentiment_created", "scenic_area_id", "sentiment", "created_at"),
        Index("ix_guide_insights_status_updated", "analysis_status", "updated_at"),
        Index("ix_guide_insights_attention_resolution_created", "needs_attention", "resolution_status", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenic_area_id: Mapped[int] = mapped_column(ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False)
    guide_session_id: Mapped[int] = mapped_column(ForeignKey("guide_sessions.id", ondelete="CASCADE"), nullable=False)
    visitor_message_id: Mapped[int] = mapped_column(ForeignKey("guide_messages.id", ondelete="CASCADE"), nullable=False)
    assistant_message_id: Mapped[int | None] = mapped_column(ForeignKey("guide_messages.id", ondelete="SET NULL"), nullable=True)
    normalized_question: Mapped[str | None] = mapped_column(String(120), nullable=True)
    primary_topic: Mapped[str | None] = mapped_column(String(50), nullable=True)
    topic_tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    issue_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    needs_attention: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    resolution_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unresolved'"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    analysis_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    analysis_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class GuideFeedback(Base):
    __tablename__ = "guide_feedbacks"
    __table_args__ = (
        UniqueConstraint("guide_session_id", name="uq_guide_feedbacks_session"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_guide_feedbacks_rating"),
        Index("ix_guide_feedbacks_scenic_created", "scenic_area_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guide_session_id: Mapped[int] = mapped_column(ForeignKey("guide_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scenic_area_id: Mapped[int] = mapped_column(ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ScenicInsightReport(Base):
    __tablename__ = "scenic_insight_reports"
    __table_args__ = (
        CheckConstraint("period_type IN ('daily', 'weekly')", name="ck_scenic_insight_reports_period_type"),
        CheckConstraint("generation_status IN ('pending', 'processing', 'completed', 'failed')", name="ck_scenic_insight_reports_generation_status"),
        Index("ix_scenic_insight_reports_scenic_period", "scenic_area_id", "period_start", "period_end"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenic_area_id: Mapped[int] = mapped_column(ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    attention_points: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    risk_findings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    generation_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    generation_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
