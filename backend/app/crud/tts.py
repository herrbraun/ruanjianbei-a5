from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.avatar import TtsProviderSetting


def ensure_tts_provider_settings(db: Session) -> list[TtsProviderSetting]:
    existing = {item.provider: item for item in db.scalars(select(TtsProviderSetting)).all()}
    defaults = (
        TtsProviderSetting(
            provider="volcengine",
            display_name="火山引擎实时语音",
            is_enabled=True,
            is_default=True,
            is_fallback=False,
            model=settings.volcengine_tts_model,
            default_voice=settings.volcengine_tts_default_voice,
            first_chunk_timeout_ms=settings.tts_first_chunk_timeout_ms,
        ),
        TtsProviderSetting(
            provider="dashscope",
            display_name="阿里云百炼千问语音",
            is_enabled=True,
            is_default=False,
            is_fallback=True,
            model=settings.guide_tts_model,
            default_voice=settings.tts_voice,
            first_chunk_timeout_ms=settings.tts_first_chunk_timeout_ms,
        ),
    )
    changed = False
    for item in defaults:
        if item.provider not in existing:
            db.add(item)
            existing[item.provider] = item
            changed = True
    if changed:
        db.commit()
    return list(db.scalars(select(TtsProviderSetting).order_by(TtsProviderSetting.provider.desc())).all())


def set_default_provider(db: Session, provider: str) -> None:
    db.execute(update(TtsProviderSetting).values(is_default=False))
    db.execute(
        update(TtsProviderSetting)
        .where(TtsProviderSetting.provider == provider)
        .values(is_default=True, is_enabled=True)
    )


def set_fallback_provider(db: Session, provider: str) -> None:
    db.execute(update(TtsProviderSetting).values(is_fallback=False))
    db.execute(
        update(TtsProviderSetting)
        .where(TtsProviderSetting.provider == provider)
        .values(is_fallback=True, is_enabled=True)
    )
