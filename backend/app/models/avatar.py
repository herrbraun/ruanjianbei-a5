from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.knowledge import ScenicArea


class DigitalHuman(Base):
    __tablename__ = "digital_humans"
    __table_args__ = (
        CheckConstraint("gender IN ('female', 'male', 'unspecified')", name="ck_digital_humans_gender"),
        CheckConstraint(
            "tts_provider IN ('volcengine', 'dashscope')",
            name="ck_digital_humans_tts_provider",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    gender: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unspecified'"))
    role_title: Mapped[str] = mapped_column(String(120), nullable=False)
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    tts_provider: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'volcengine'"))
    tts_voice: Mapped[str] = mapped_column(String(100), nullable=False)
    tts_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    variants: Mapped[list["AvatarVariant"]] = relationship(back_populates="digital_human", cascade="all, delete-orphan")


class TtsProviderSetting(Base):
    __tablename__ = "tts_provider_settings"
    __table_args__ = (
        CheckConstraint("provider IN ('volcengine', 'dashscope')", name="ck_tts_provider_settings_provider"),
        CheckConstraint(
            "first_chunk_timeout_ms BETWEEN 500 AND 10000",
            name="ck_tts_provider_settings_first_chunk_timeout",
        ),
    )

    provider: Mapped[str] = mapped_column(String(30), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    default_voice: Mapped[str] = mapped_column(String(100), nullable=False)
    first_chunk_timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("4500"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AvatarVariant(Base):
    __tablename__ = "avatar_variants"
    __table_args__ = (
        UniqueConstraint("digital_human_id", "outfit_name", "version", name="uq_avatar_variants_human_outfit_version"),
        CheckConstraint("validation_status IN ('ready', 'failed')", name="ck_avatar_variants_validation_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    digital_human_id: Mapped[int] = mapped_column(ForeignKey("digital_humans.id", ondelete="CASCADE"), nullable=False, index=True)
    outfit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'v1'"))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ready'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    digital_human: Mapped[DigitalHuman] = relationship(back_populates="variants")
    scenic_configs: Mapped[list["ScenicAvatarConfig"]] = relationship(back_populates="avatar_variant", cascade="all, delete-orphan")


class ScenicAvatarConfig(Base):
    __tablename__ = "scenic_avatar_configs"
    __table_args__ = (
        UniqueConstraint("scenic_area_id", "avatar_variant_id", name="uq_scenic_avatar_configs_area_variant"),
        Index("ix_scenic_avatar_configs_area_enabled_sort", "scenic_area_id", "is_enabled", "sort_order"),
        Index(
            "uq_scenic_avatar_configs_one_default",
            "scenic_area_id",
            unique=True,
            postgresql_where=text("is_default AND is_enabled"),
            sqlite_where=text("is_default AND is_enabled"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenic_area_id: Mapped[int] = mapped_column(ForeignKey("scenic_areas.id", ondelete="CASCADE"), nullable=False, index=True)
    avatar_variant_id: Mapped[int] = mapped_column(ForeignKey("avatar_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    scenic_area: Mapped["ScenicArea"] = relationship()
    avatar_variant: Mapped[AvatarVariant] = relationship(back_populates="scenic_configs")
