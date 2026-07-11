from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func, text
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
